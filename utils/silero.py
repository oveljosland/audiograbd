import subprocess
import logging
import time
from pathlib import Path
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
from utils.transcode import EXTENSIONS

logger = logging.getLogger(__name__)



def get_timestamps(path: Path, model=None):
	"""Return speech timestamps for a file or directory."""
	path = Path(path)

	if model is None: # load model once
		model = load_silero_vad()

	if path.is_dir():
		timestamps = {}
		for p in sorted(path.rglob("*")):
			if p.suffix.lower() not in EXTENSIONS:
				continue
			timestamps[str(p)] = get_timestamps(p, model=model)
		return timestamps

	audio = read_audio(str(path))
	return get_speech_timestamps(audio, model, return_seconds=True)



def expr_from_timestamp(timestamps) -> str:
	"""Make FFmpeg expression from timestamp."""
	if not timestamps:
		return None

	expressions = []

	for seg in timestamps:
		start, end = float(seg["start"]), float(seg["end"])
		expressions.append(f"between(t,{start:.3f},{end:.3f})")
	return "+".join(expressions)



def mute_segments(path: Path, timestamps):
	"""Mute speech segments of a file or dir of files from timestamps."""
	path = Path(path)

	if not timestamps:
		return path

	expression = expr_from_timestamp(timestamps)
	if not expression:
		return path

	# input : audio.wav
	# output: audio.muted.wav
	output_path = path.with_name(f"{path.stem}.muted{path.suffix}")
	cmd = [
		"ffmpeg", "-y", "-i",
		str(path),
		"-af", f"volume=enable='{expression}':volume=0",
		str(output_path),
	]

	subprocess.run(cmd, check=True)
	output_path.replace(path)



def _detect_and_mute(path: Path, config, model=None):
	"""Detect speech segments in audio files and mute them."""
	path = Path(path)
	if model is None: # load model once
		model = load_silero_vad()

	if path.is_dir():
		results = {}
		for p in sorted(path.rglob("*")):
			if p.suffix.lower() not in EXTENSIONS:
				continue
			try:
				timestamps = get_timestamps(p, model=model)
				if timestamps:
					mute_segments(p, timestamps)
				results[str(p)] = timestamps
			except Exception as e:
				logger.warning(f"Skipping {p}: {e}")
				# TODO: decide to skip or delete the file
				# path.unlink(missing_ok=True)
		return results

	try: # single file
		timestamps = get_timestamps(path, model=model)
		if timestamps:
			mute_segments(path, timestamps)
		return timestamps
	except Exception as e:
		logger.warning(f"Skipping {path}: {e}")
		# TODO: decide to skip or delete the file
		# path.unlink(missing_ok=True)
		return []




def detect_and_mute(path, config):
	mute = config.get("speech-removal", {})
	if mute.get("enabled", False):
		logger.info("Speech removal enabled")
		start = time.time()
		try:
			processed = _detect_and_mute(path, config)
			logger.info(f"Speech muted ({time.time() - start:.2f}s)")
			for p, ts in processed.items():
				logger.info(f"{Path(p).name}: {len(ts)} segments")
		except Exception as e:
			logger.error(f"Speech detection failed: {e}")
	else:
		logger.info("Speech removal disabled")