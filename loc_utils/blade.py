import os, sys
import pathlib
import importlib
import adsk.core, adsk.fusion, traceback
import numpy as np
import yaml

# Local imports
from .naca import NACA4
from .profile import Profile

class Blade():
    def __init__(self, app, blade_config: dict) -> None:
        self.naca : NACA4 = None
        self.app = app
        self.ui = app.userInterface
        self.rails = (adsk.core.ObjectCollection.create(), adsk.core.ObjectCollection.create())  # Two extrusion rails, collection of Points
        self.angle = blade_config['angle']
        self.profiles = blade_config['profiles']

    def __createOffsetPlane(self, offset) -> adsk.fusion.ConstructionPlane:
        """Create a new offset plane and return it."""
        design = self.app.activeProduct
        rootComp = design.rootComponent
        planes = rootComp.constructionPlanes
        planeInput = planes.createInput()
        planeInput.setByOffset(
            rootComp.xYConstructionPlane, 
            adsk.core.ValueInput.createByReal(offset)
        )
        return planes.add(planeInput)

    def __createOffsetPlanesAndGenerateProfilesObject(self):
        """Create all the offset planes from the interpretation of the self.profiles dict."""
        self.profiles = []
        profiles = self.profiles
        for profile in profiles:
            res = Profile(
                plane = self.__createOffsetPlane(profile['offset']),
                naca = NACA4(profile['naca']),
                c = profile['c'],
                angle = profile['angle'],
                offset = profile['offset'],
                colinear_offset = profile['colinear_offset']
            )
            self.profiles.append(res)
            print(res)

    # <!-- DEPRECATED -->

    # @staticmethod
    # def rotate(points: np.ndarray, angle: float): # TODO : implement it in Profile class
    #     angle_rad = angle / 180 * np.pi
    #     derivative = np.tan(angle_rad)
    #     return np.array([points[:, 0], points[:, 1] + derivative*points[:, 0]]).T # Works because leading edge is at (0, 0) 

    # def transformedPointsFromProfile(self, profile: Profile): # TODO : implement it in Profile class
    #     return self.rotate(
    #         profile.generatePoints() * profile.c, # c scaling (corde)
    #         profile.angle # angle rotation
    #     )

    # <!-- END DEPRECATED -->

    def __generateProfile(self, profile: Profile):
        """Generates a profile in the 3D modeling from a profile object."""

        design = self.app.activeProduct
        rootComp = design.rootComponent  # root component (contains sketches, volumnes, etc)
        
        # Getting the plane object created earlier
        plane = profile.plane
        
        # Creating a sketch from the plane
        sketch = rootComp.sketches.add(plane)  # in the XZ plane
        # Creating a point collection
        points = adsk.core.ObjectCollection.create()  # object collection that contains points

        # Define the points the spline with fit through.
        naca_points = profile.getPoints()

        # Generating the rails points to guide the future loft (took the 2 outer points)
        self.rails[0].add(adsk.core.Point3D.create(*naca_points[0], profile.offset))
        self.rails[1].add(adsk.core.Point3D.create(*naca_points[profile.n-1], profile.offset))

        # Adding the points to the collection (i.e. to the sketch)
        for x, y in naca_points:
            p = adsk.core.Point3D.create(x, y, 0)
            points.add(p)

        # Drawing the spline
        spline = sketch.sketchCurves.sketchFittedSplines.add(points)
        profile.sketch = sketch

    def __generateProfiles(self):
        """Generates all the profiles in the 3D modeling from the self.config dict."""
        for profile in self.profiles:
            self.__generateProfile(profile) 

        # generate rails
        design = self.app.activeProduct
        rootComp = design.rootComponent  # root component (contains sketches, volumnes, etc)
        verticalSketch = rootComp.sketches.add(rootComp.xYConstructionPlane)
        print(self.rails)
        self.c1, self.c2 = [verticalSketch.sketchCurves.sketchFittedSplines.add(pts) for pts in self.rails]
        
    
    def __loftProfiles(self) -> None:
        """Lofts together all profiles i.e. form the solid defined by the profiles"""

        design = self.app.activeProduct
        rootComp = design.rootComponent
        
        # Creating the different objects to call the loft function
        loftFeats = rootComp.features.loftFeatures
        loftInput = loftFeats.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    
        # Create rails (guides) in order to avoid creating funny looking shapes when lofting
        loftRails = loftInput.centerLineOrRails
        loftRails.addRail(self.c1)
        loftRails.addRail(self.c2)

        # Adding all the profiles to the loft
        loftSectionsObj = loftInput.loftSections
        [loftSectionsObj.add(sketch.profiles.item(0)) for sketch in [profile.sketch for profile in self.profiles]]

        # Setting the loft parameters
        loftInput.isSolid = True
        loftInput.isClosed = False
        loftInput.isTangentEdgesMerged = True

        # Creating the loft
        loftFeats.add(loftInput)

    def __rotateSelf(self) -> None:
        """Rotates the blade around the X axis by self.angle degrees."""
        raise NotImplementedError("This method is not implemented yet.") # TODO : implement it, code generated by copilot below
        # design = self.app.activeProduct
        # rootComp = design.rootComponent
        # transform = adsk.core.Matrix3D.create()
        # transform.setToRotation(self.angle, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Point3D.create(0, 0, 0))
        # rootComp.transformFeatures.addSimple(transform)

    def build(self) -> None:
        """Builds the blade from the config dict."""
        self.__createOffsetPlanesAndGenerateProfilesObject()
        self.__generateProfiles()
        self.__loftProfiles()
        # self.__rotateSelf() # TODO : implement it