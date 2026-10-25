"""Generate a printable ArUco marker; measure the black outer square after printing."""
import cv2
from pathlib import Path
image=cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),0,600)
image=cv2.copyMakeBorder(image,80,80,80,80,cv2.BORDER_CONSTANT,value=255)
Path('docs').mkdir(exist_ok=True)
cv2.imwrite('docs/marker-0.png',image)
print('Print docs/marker-0.png on flat card. Measure black-square side; supply --marker-side-m. Do not wrap it around a can.')
