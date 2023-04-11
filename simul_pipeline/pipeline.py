import sys
import time
# this adds BladeGenerator to the PYTHONPATH
sys.path.append("..\\..\\")

import os, shutil
import signal
import psutil
import glob
import subprocess
from pathlib import Path
import numpy as np
import gmsh
from BladeGenerator.loc_utils.naca import NACA4
from .gmsh_api import MeshGenerator


DIR = Path().resolve()
TEMP_DIR = DIR / "temp"
BOUNDARY_LAYER_BOX2_DEFAULT = [5.0, 0.4]


def delete_folder_contents(folder_path, delete_directory=False):
    if delete_directory:
        shutil.rmtree(folder_path)
    else:
        for f in glob.glob(str(folder_path / "*")):
            os.remove(f)


class Pipeline():
    def __init__(self, mtc_dir: str, gmsh2mtc_path: str, boundary_layer_dir: str, naca_simulator_dir: str) -> None:
        self.airfoil_mesh_generator = None

        self.airfoil_mesh_name = "airfoil.msh"
        self.airfoil_mesh_path = TEMP_DIR / self.airfoil_mesh_name
        self.airfoil_mtc_path = self.airfoil_mesh_path.with_suffix(".t")

        self.mtc2gmsh_path = Path(gmsh2mtc_path)
        self.mtc_path = Path(mtc_dir) / "mtc.exe"
        self.boundary_layer_dir = Path(boundary_layer_dir)
        self.naca_simulator_dir = Path(naca_simulator_dir)

        # Create temp directory if it doesn't exist
        Path(DIR / "temp").mkdir(parents=True, exist_ok=True)
        delete_folder_contents(TEMP_DIR)

    def generate_airfoil_mesh(self, h: float, NACA: NACA4, alpha=0.0) -> None:
        self.airfoil_mesh_generator = MeshGenerator(h, NACA, alpha)

    def gmsh_to_mtc(self) -> None:
        # This is suboptimal (calling a python script with subprocess)
        print("\nConverting gmsh mesh to mtc mesh...")
        print(f"{self.airfoil_mesh_path} -> {self.airfoil_mtc_path}")
        subprocess.run([
            "python",
            self.mtc2gmsh_path, 
            self.airfoil_mesh_path, 
            self.airfoil_mtc_path
        ])

    def process_airfoil_mtc(self) -> None:
        print(f"Processing {self.airfoil_mtc_path}...")
        p = subprocess.Popen([self.mtc_path, self.airfoil_mtc_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate(input=b'0\n')

    def generate_boundary_layer_mesh(self, alpha, timeout=30) -> None:
        Pipeline.warn("this will override the previous results of BoundaryLayerMesh")
        # move the mtc file to the boundary layer directory
        shutil.copy(self.airfoil_mtc_path, self.boundary_layer_dir / "naca.t")

        # configure the Box2 file (it must be resized when alpha != 0)
        with open(self.boundary_layer_dir / "Box2.txt", "w") as f:
            x, y = BOUNDARY_LAYER_BOX2_DEFAULT
            f.write(f"{x} {y*(1 + np.sin(alpha))}")

        # delete old results
        delete_folder_contents(self.boundary_layer_dir / "Output")

        # Start the process for a given number of seconds (adjust timeout if needed)
        print(f"Starting BoundaryLayerMesh... (timemout = {timeout}s)")
        proc = subprocess.Popen([self.boundary_layer_dir / "LANCER.bat"], cwd=self.boundary_layer_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(timeout)
        
        # kill the main and generated process
        print("Killing BoundaryLayerMesh...")
        proc.kill()
        for p in psutil.process_iter():
            if p.name() == "modeles.exe":
                p.kill()

        # move the results to the temp directory
        latest_file = sorted(glob.glob(str(self.boundary_layer_dir / "Output" / "*.t")))[-1]
        print(f"Using latest file: {Path(latest_file).name}")
        shutil.copy(latest_file, TEMP_DIR / "boundary_layer.t")

    def run_simulation(self) -> None:
        # move boundary layer file and airfoil file to the naca simulator directory
        Pipeline.warn("this will override the previous results of NACASimulator")
        shutil.copy(TEMP_DIR / "airfoil.t", self.naca_simulator_dir / "naca.t")
        shutil.copy(TEMP_DIR / "boundary_layer.t", self.naca_simulator_dir / "domaine.t")

        delete_folder_contents(self.naca_simulator_dir / "resultats", delete_directory=True)

        # Start the process
        print("Starting NACASimulator...")
        proc = subprocess.Popen([self.naca_simulator_dir / "LANCER.bat"], 
                                cwd=self.naca_simulator_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)




    def save_mesh(self):
        self.airfoil_mesh_generator.saveMesh(str(TEMP_DIR / self.airfoil_mesh_name))

    def warn(message: str) -> None:
        print("WARNING: " + message)
        if input("Continue ? [Y/n]").lower() not in ["", "y", " "]:
            raise SystemExit(1, "User stopped execution")