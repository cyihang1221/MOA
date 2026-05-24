import os
import subprocess
import tempfile
import glob


# ============================= openms 实现 =============================
def isotope_annotation_openms_impl(
    input_dir: dir,
    output_dir: str,
    mass_error_ppm: float = 10.0
):
    os.makedirs(output_dir, exist_ok=True)
    output_files = []

    for input_file in os.listdir(input_dir):
        input_path = os.path.join(input_dir, input_file)
        base = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base}_isotope.featureXML")

        cmd = f"""
#!/bin/bash
set -e
FeatureFinderIsotope \\
    -in "{input_file}" 
    -out "{output_file}" \\
    -algorithm:mtd:mass_error_ppm {mass_error_ppm}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(cmd)
            script = f.name

        try:
            subprocess.run(["bash", script], check=True, capture_output=True)
            
        finally:
            os.unlink(script)
            os.unlink(input_path)
