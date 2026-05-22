import time
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


"""
TODO:
- Consider doing the transcoding in parallell. Found an example online:
	```
	from concurrent.futures import ProcessPoolExecutor
	from pathlib import Path
	import subprocess

	def transcode(path):
		subprocess.run([
			"ffmpeg", "-y", "-i", str(path),
			"-c:a", "flac", str(path.with_suffix(".flac"))
		], check=True)

	files = list(Path("audio").glob("*.mp3"))

	with ProcessPoolExecutor() as ex:
		ex.map(convert, files)
	```
"""


EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".opus"}



def skip(codec: str, ext: str) -> bool:
	"""Returns True if the file should skip transcoding."""
	skip = {
		"opus": ".opus",
		"flac": ".flac",
	}
	return skip.get(codec) == ext



def remove_original(original: Path, new: Path):
	"""Remove the original file after succesful transcoding."""
	if new.exists() and new != original:
		original.unlink(missing_ok=True)



def transcode_opus(path: Path, config):
	"""Transcode audio into Opus with FFmpeg.
	Gets parameters from the config file,
	and removes original file after transcoding.
	"""
	if not path.is_file():
		raise FileNotFoundError(path)

	if path.suffix.lower() == ".opus":
		return path

	output = path.with_suffix(".opus")

	cmd = [
		"ffmpeg",
		"-y",
		"-i",
		str(path),
		"-ac", "1", # mono
		"-ar", str(config["sample_rate"]),
		"-c:a", "libopus",
		"-b:a", f'{config["bitrate_kbps"]}k',
		str(output)
	]

	subprocess.run(cmd, check=True)
	remove_original(path, output)
	return output



def transcode_flac(path: Path, config):
	"""Transcode audio into FLAC with FFmpeg.
	Gets parameters from the config file,
	and removes original file after transcoding.
	"""
	if not path.is_file():
		raise FileNotFoundError(path)

	if path.suffix.lower() == ".flac":
		return path

	output = path.with_suffix(".flac")

	cmd = [
		"ffmpeg",
		"-y",
		"-i", str(path),
		"-ac", "1", # mono
		"-c:a", "flac",
		str(output)
	]

	subprocess.run(cmd, check=True)
	remove_original(path, output)
	return output


TRANSCODERS = {
	"opus": transcode_opus,
	"flac": transcode_flac,
}


def _transcode(path: Path, config) -> Path:
	"""Transcode media into the codec specified in the config file.
	Codecs not listed in `EXTENSIONS` will be ignored.
	"""

	path = Path(path)

	if path.is_dir():
		for file_path in path.rglob("*"):
			if file_path.is_file():
				try:
					_transcode(file_path, config)
				except Exception as e:
					logger.warning(f"Skipping unrecognised file {file_path}: {e}")
					"""TODO: decide to skip or delete the file"""
					# path.unlink(missing_ok=True)
		return path

	ext = path.suffix.lower()

	if ext not in EXTENSIONS:
		return path

	codec = config["transcoding"]["audio"]["codec"]

	if skip(codec, ext):
		return path

	handler = TRANSCODERS.get(codec)
	if not handler:
		raise ValueError(f"unsupported codec: {codec}")

	try:
		return handler(path, config["transcoding"]["audio"])
	except Exception as e:
		logger.warning(f"Skipping unrecognised file {path}: {e}")
		"""TODO: decide to skip or delete the file"""
		# path.unlink(missing_ok=True)
		return path



def transcode(path, config):
	tc = config.get("transcoding", {})
	if tc.get("enabled", False):
		logger.info("Transcoding enabled")
		start = time.time()
		try:
			_transcode(path, config)
			logger.info(f"Transcoding completed ({time.time() - start:.2f}s)")
		except Exception as e:
			logger.error(f"Transcoding failed: {e}")
	else:
		logger.info("Transcoding disabled")
