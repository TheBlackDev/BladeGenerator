import os, sys
import pathlib
import importlib
import adsk.core, adsk.fusion, traceback

# install packages
def installPackages(packages_to_install):
    try:
        [importlib.import_module(pack[1]) for pack in packages_to_install]
    except:
        install_str = sys.path[0] +'\\Python\\python.exe -m pip install ' + ' '.join([pack[0] for pack in packages_to_install])
        os.system('cmd /c "' + install_str + '"')
        [importlib.import_module(pack[1]) for pack in packages_to_install]

installPackages([('numpy', 'numpy'), ('gmsh', 'gmsh'), ('pyyaml', 'yaml')]) # list format : [(pip_name, import_name), ...]

import numpy as np
import yaml

# Local imports
from .loc_utils import *

DIR = pathlib.Path(__file__).parent.resolve()

class NACAInterface():
    def __init__(self, app) -> None:
        self.naca : NACA4 = None
        self.app = app
        self.ui = app.userInterface
        self.points = []  # TODO: replace with NACA object

    def prompt_config_file(self) -> None:

        file_ok = False
        while not file_ok:

            # Prepare file input dialog
            fileDlg = self.ui.createFileDialog()
            fileDlg.isMultiSelectEnabled = False
            fileDlg.title = 'Select a .yml file'
            fileDlg.filter = 'YAML Files (*.yml, *.yaml)'
            
            # Show file input dialog
            dlgResult = fileDlg.showOpen()
            if dlgResult == adsk.core.DialogResults.DialogOK:
                self.filepath = fileDlg.filename
            else:
                raise SystemExit(1, 'No config file selected')
            
            # Confirmation dialog
            status = self.ui.messageBox(f'Use {self.filepath} as config file ?', 'Confirm', adsk.core.MessageBoxButtonTypes.YesNoButtonType)

            if status == adsk.core.DialogResults.DialogYes:
                file_ok = True

    def interpret_config_file(self):
        with open(self.filepath, 'r') as stream:
            self.config = yaml.safe_load(stream.read())
        

    # def points_from_dat(self, filename):
    #     with open(f'{DIR}\\{filename}', 'r') as f:
    #         lines = f.readlines()
    #     self.points = PointGenerator(lines).getPoints()

    @staticmethod
    def pointsFromNACA(naca : NACA4):
        return PointGenerator(naca).getPoints()

    def addNACAtoPlane(self, plane = None):
        design = self.app.activeProduct
        rootComp = design.rootComponent  # root component (contains sketches, volumnes, etc)
        if plane is None:
            plane = rootComp.xYConstructionPlane
        sketch = rootComp.sketches.add(plane)  # in the XZ plane
        points = adsk.core.ObjectCollection.create()  # object collection that contains points

        # Define the points the spline with fit through.
        for x, y in self.points:
            points.add(adsk.core.Point3D.create(x, y, 0))
        
        # draw the spline
        spline = sketch.sketchCurves.sketchFittedSplines.add(points)
        return sketch

    def createOffsetPlane(self, offset):
        # TODO: create new plane at offset	
        design = self.app.activeProduct
        rootComp = design.rootComponent
        planes = rootComp.constructionPlanes
        planeInput = planes.createInput()
        planeInput.setByOffset(
            rootComp.xYConstructionPlane, 
            adsk.core.ValueInput.createByReal(offset)
        )
        return planes.add(planeInput)
    
    def loftProfiles(self, profileSketches):
        # Lofts together all profiles
        # TODO: see if loft is the best way to do this
        design = self.app.activeProduct
        rootComp = design.rootComponent
        
        loftFeats = rootComp.features.loftFeatures
        loftInput = loftFeats.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        loftSectionsObj = loftInput.loftSections
        [loftSectionsObj.add(sketch.profiles.item(0)) for sketch in profileSketches]

        loftInput.isSolid = True
        loftInput.isClosed = False
        loftInput.isTangentEdgesMerged = True
        loftFeats.add(loftInput)


def run(context):
    app = adsk.core.Application.get()
    
    # Make the user enter a NACA input
    interface = NACAInterface(app)

    profileSketches = []
    for offset in range(0, 15, 5):
        interface.prompt_config_file()
        interface.interpret_config_file()
        interface.pointsFromNACA()
        newPlane = interface.createOffsetPlane(offset/10)
        profileSketches.append(interface.addNACAtoPlane(newPlane))
    
    interface.loftProfiles(profileSketches)