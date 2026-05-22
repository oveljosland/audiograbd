import subprocess
import logging
import time

logger = logging.getLogger(__name__)

# uv run birdnet-analyze input/ -o output/

def birdnet_analyse(input_path, output_path, config) -> None:
	"""Analyse a file or directory with BirdNET."""
	birdnet = config.get("birdnet", {})
	if birdnet.get("enabled", False):
		logger.info("birdnet-analyzer enabled")
		start = time.time()
		try:
			subprocess.run([
				"uv", "run", "birdnet-analyze",
				str(input_path),
				"-o", str(output_path)],
				text=True
			)
			logger.info(f"Analysis completed ({time.time() - start:.2f}s)")

		except Exception as e:
			logger.error(f"birdnet-analyzer failed: {e}")
	else:
		logger.info("birdnet-analyzer disabled")