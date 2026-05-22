import os
import re
import json
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)



def get_block_devices_json():
	"""Returns a list of block devices as JSON."""
	output = subprocess.run([
		"lsblk", "-J", "-b", # print size in bytes
		"-o", "NAME,TYPE,SIZE,RM,FSTYPE,MOUNTPOINTS" # only relevant fields
		],
		capture_output=True,
		text=True
	)
	return json.loads(output.stdout)



def get_removable_devices():
	"""Returns the paths of all removable block devices."""
	devices = get_block_devices_json()
	removable = []

	for device in devices['blockdevices']:
		if device.get('type') != 'disk':
			continue # skip non-disks
		if not device.get('rm'):
			continue # skip non-removable
		if not device.get('size', 0):
			continue # skip empty

		if not device.get('children'):
			continue # skip if no partitions

		removable.append(f"/dev/{device['name']}")

	return removable


def get_partitions(path, return_largest=False):
	"""Returns the partitions of the device.
	Optionally return the largest partition.
	"""
	devices = get_block_devices_json()
	for device in devices['blockdevices']:
		if f"/dev/{device['name']}" == path:
			partitions = device.get("children", [])
			if return_largest and partitions:
				largest = max(partitions, key=lambda p: p["size"])
				return [f"/dev/{largest['name']}"]
			return [f"/dev/{p['name']}" for p in partitions]
	return []



def mount(path):
	""" Mount the device, and return its mountpoint. """
	output = subprocess.run([
		"udisksctl", "mount", "-b", path
	],
	capture_output=True,
	text=True
	)
	if "already mounted" in output.stderr or output.returncode != 0:
		# find mount point
		devices = get_block_devices_json()
		for device in devices['blockdevices']:
			for child in device.get('children', []):
				if f"/dev/{child['name']}" == path:
					mounts = child.get('mountpoints', [])
					if mounts and mounts[0]:
						return mounts[0]
		# failed to find mount point
		raise RuntimeError(f"failed to mount {path}: {output.stderr}")
	
	return output.stdout.split()[-1]



def unmount(path):
	""" Unmount the device. """
	return subprocess.run([
		"udisksctl", "unmount", "-b", path
	],
	capture_output=True,
	text=True
	).stderr # return error



def mount_all_partitions(path):
	"""Mount all the partitions of the device, return their mountpoints."""
	partitions = get_partitions(path)
	mount_points = []
	for partition in partitions:
		mount_point = mount(partition)
		mount_points.append(mount_point)
	return mount_points



def unmount_all_partitions(path):
	"""Unmount all partitions of the device."""
	for device in path:
		unmount(device)



def transfer(mount_points, destination, copy=False):
	"""Move all files from the mount points to `destination`.
	Returns a list of the absolute destination paths.
	"""

	destination_path = Path(destination).resolve()
	destination_path.mkdir(parents=True, exist_ok=True)

	moved_files = []
	for mount_point in mount_points:
		src_root = Path(mount_point)
		if not src_root.exists():
			raise FileNotFoundError(f"Mount point not found: {src_root}")

		if src_root.is_file():
			target = destination_path / src_root.name
			target.parent.mkdir(parents=True, exist_ok=True)
			if copy:
				shutil.copy2(str(src_root), str(target))
			else:
				shutil.move(str(src_root), str(target))
			moved_files.append(str(target.resolve()))
			continue

		for src in sorted(src_root.rglob("*")):
			if not src.is_file():
				continue

			relative_path = src.relative_to(src_root)
			target = destination_path / relative_path
			target.parent.mkdir(parents=True, exist_ok=True)
			if copy:
				shutil.copy2(str(src), str(target))
			else:
				shutil.move(str(src), str(target))
			moved_files.append(str(target.resolve()))

	return moved_files



def transfer_from_all(dst, copy=False):
	"""Move all files from all removable devices to `dst`.
	Files will be kept if copy is True.
	Returns a list of the absolute destination paths.
	"""
	device_paths = get_removable_devices()
	logger.info(f"Found removable devices: {device_paths}")

	if not device_paths:
		raise RuntimeError("No removable devices found")

	moved = []
	for device_path in device_paths:
		partitions = get_partitions(device_path)
		logger.info(f"Found partitions for {device_path}: {partitions}")

		mount_points = mount_all_partitions(device_path)
		logger.info(f"Mount points for {device_path}: {mount_points}")

		if copy:
			logger.info(f"Copying data to {dst}")
		else:
			logger.info(f"Moving data to {dst}")

		moved.extend(transfer(mount_points, dst, copy=copy))

	logger.info(f"Moved {len(moved)} files to: {dst}")
	return moved
