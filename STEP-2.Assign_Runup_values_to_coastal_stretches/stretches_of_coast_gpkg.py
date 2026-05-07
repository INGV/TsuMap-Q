from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
    QgsProcessingMultiStepFeedback
)
import processing
import os


class ExportStretchToGPKG(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):

        self.addParameter(QgsProcessingParameterVectorLayer(
            'INPUT',
            'Layer con stretch_ID',
            types=[QgsProcessing.TypeVectorAnyGeometry]
        ))

        self.addParameter(QgsProcessingParameterField(
            'FIELD',
            'Campo stretch_ID',
            parentLayerParameterName='INPUT',
            type=QgsProcessingParameterField.Numeric
        ))

        self.addParameter(QgsProcessingParameterFileDestination(
            'OUTPUT',
            'GeoPackage di output',
            fileFilter='GeoPackage (*.gpkg)'
        ))

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)

        layer = self.parameterAsVectorLayer(parameters, 'INPUT', context)
        field_name = self.parameterAsString(parameters, 'FIELD', context)
        gpkg_path = self.parameterAsString(parameters, 'OUTPUT', context)

        # Se esiste già, lo elimino (opzionale)
        if os.path.exists(gpkg_path):
            os.remove(gpkg_path)

        # Recupero ID unici
        unique_ids = set()
        for f in layer.getFeatures():
            unique_ids.add(f[field_name])

        total = len(unique_ids)
        current = 0

        for uid in unique_ids:

            if feedback.isCanceled():
                break

            current += 1
            feedback.setProgress(int(current / total * 100))

            layer_name = f"stretch_{int(uid)}"

            expr = f'"{field_name}" = {uid}'

            alg_params = {
                'INPUT': layer,
                'EXPRESSION': expr,
                'OUTPUT': f"{gpkg_path}|layername={layer_name}"
            }

            processing.run(
                'native:extractbyexpression',
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )

        return {'OUTPUT': gpkg_path}

    def name(self):
        return 'export_stretch_to_gpkg'

    def displayName(self):
        return 'Export stretch_ID in GeoPackage (layer multipli)'

    def group(self):
        return 'Custom scripts'

    def groupId(self):
        return 'customscripts'

    def createInstance(self):
        return ExportStretchToGPKG()