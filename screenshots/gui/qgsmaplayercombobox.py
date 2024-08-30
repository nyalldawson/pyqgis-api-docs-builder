from pathlib import Path
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer
)
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import QPoint
from qgis.PyQt.QtGui import QImage, QPainter
from qgis.PyQt.QtWidgets import QWidget,QVBoxLayout


def generate_screenshot(dest_path: Path):
    layer = QgsVectorLayer('Point', 'A point layer', 'memory')
    layer2 = QgsVectorLayer('Line', 'A line layer', 'memory')
    raster = QgsRasterLayer('x', 'Raster layer')

    QgsProject.instance().addMapLayers([layer, layer2, raster])

    w = QWidget()
    w.setLayout(QVBoxLayout())
    combo = QgsMapLayerComboBox()
    w.layout().addWidget(combo)
    w.layout().addStretch()
    w.setFixedWidth(300)
    w.setFixedHeight(100)
    #combo.showPopup()
    im = QImage(w.size(), QImage.Format_RGB32)
    painter = QPainter(im)
    w.render(painter)
    #combo.view().top()
#    combo.view().render(painter, QPoint(40, 40)) #QPoint(combo.view().pos().x(), combo.view().pos().y()))
    painter.end()

    im.save((dest_path / 'qgsmaplayercombobox.png').as_posix())


    return "\n.. image:: qgsmaplayercombobox.png\n"
