"""
Run with:
	uv run main.py

Run and serve processed files:
	uv run main.py --serve-port 9000
"""

import os
import time
import uuid
import subprocess
import logging
import argparse
import threading

from pathlib import Path

from utils.logger import configure_logging
from utils.wakealarm import set_wakealarm, disable_wakealarm
from utils.device import transfer_from_all
from utils.transcode import transcode
from utils.config import load_config, load_backup
from utils.storage import GCSProvider, Sigma2Provider, upload
from utils.silero import detect_and_mute
from utils.server import serve
from utils.birdnet import birdnet_analyse


logger = logging.getLogger(__name__)


"""
TODO:

What should be done if there are no devices connected?

Suggestion:
	set_wakealarm(5)
	halt()
"""


def halt():
	"""Tell the OS to halt the system.
	The `POWER_OFF_ON_HALT` EEPROM flag must be set to `1`.
	"""
	try:
		subprocess.run(["systemctl", "halt"], check=True)
	except Exception as e:
		logger.error(f"failed to halt: {e}")



def create_upload_dir(config):
	"""Create upload dir in `/tmp` with a project name,
	timestamp and UUID. The upload dir is not peristent."""
	name = config.get('project_name', 'audiograb')
	date = time.strftime(config.get('date_time_format', "%Y%m%d-%H%M%S"))
	base = Path("/tmp") / f"{name}-{date}-{str(uuid.uuid4())[:8]}"
	(base / "data").mkdir(parents=True, exist_ok=True)
	(base / "logs").mkdir(parents=True, exist_ok=True)
	(base / "results").mkdir(parents=True, exist_ok=True)
	logger.info(f"Created upload directory at {base}")
	return base





if __name__ == "__main__":

	start_time = time.time()

	parser = argparse.ArgumentParser(
		description=
		"audiograbd - process and transmit data from wildlife recorders"
	)
	parser.add_argument(
		'--serve-port', type=int, default=None, help="Serve processed files"
	)
	args = parser.parse_args()


	try:
		#config = load_config()
		config = load_backup() # load the config in this repo
		
	except RuntimeError as e:
		logger.error(f"Failed to load config: {e}")
		if config.get('scheduler', {}).get('enabled', False):
			logger.info(f"Waking up in 10 minutes to try again...")
		set_wakealarm(10)
		halt()

	upload_dir = create_upload_dir(config)
	result_dir = upload_dir / "results"
	data_dir = upload_dir / "data"
	logs_dir = upload_dir / "logs"
	

	project_name = config.get('project_name', 'audiograb')
	configure_logging(config, file=logs_dir / f"{project_name}.log")
	

	try:
		start = time.time()
		moved = transfer_from_all(data_dir, copy=True) # copy=False when deployed
		logger.info(f"Offloaded completed ({time.time() - start:.2f}s)")
	except RuntimeError as e:
		logger.error(f"Failed transfer to {upload_dir}: {e}")


	birdnet = config.get("birdnet", {})
	if birdnet.get("enabled", False):
		logger.info("birdnet-analyzer enabled")
		try:
			birdnet_analyse(data_dir, result_dir)

		except Exception as e:
			logger.error(f"birdnet-analyzer failed: {e}")
	else:
		logger.info("birdnet-analyzer disabled")
	

	silero = config.get("speech-removal", {})
	if silero.get("enabled", False):
		logger.info("Speech removal enabled")
		start = time.time()
		try:
			processed = detect_and_mute(data_dir)
			logger.info(f"Speech segments muted ({time.time() - start:.2f}s)")
			for p, ts in processed.items():
				logger.info(f"{Path(p).name}: {len(ts)} speech segments")
		except Exception as e:
			logger.error(f"Speech detection failed: {e}")
	else:
		logger.info("Speech removal disabled")
	
	
	start = time.time()
	
	transcode(data_dir, config)
	logger.info(f"Transcoding completed ({time.time() - start:.2f}s)")
	

	# start web server if audiograbd was run with --serve-port <port> 
	if args.serve_port:
		server = threading.Thread(
			target=serve, args=(upload_dir, args.serve_port),
			daemon=True
		)
		server.start()
		try:
			while True:
				time.sleep(1)
		except KeyboardInterrupt:
			logger.info("Stopping web server...")


	upload(upload_dir, config)
	
	
	
	scheduler = config.get('scheduler', {})
	if scheduler.get('enabled'):
		interval = scheduler.get('interval_minutes')
		if interval is None or interval < 0:
			logger.warning(f"Invalid wake interval ({interval})")
		else:
			logger.info(f"Uptime: {time.time() - start_time:.2f} seconds")
			logger.info(f"Next wake alarm scheduled in {interval} minute(s)")
			set_wakealarm(interval)

			# time to die
			logger.info(f"Halting (uptime {time.time() - start_time:.2f}s)")
			#halt()
			exit(0)

	
	logger.info(f"Halting (uptime {time.time() - start_time:.2f}s)")
	exit(0)


