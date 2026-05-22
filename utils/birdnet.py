import subprocess

# uv run birdnet-analyze input/ -o output/

def birdnet_analyse(input_path, output_path) -> None:
	"""Analyse a file or directory with BirdNET."""
	subprocess.run([
		"uv", "run", "birdnet-analyze",
		str(input_path), "-o", str(output_path)
		],
		text=True
	)