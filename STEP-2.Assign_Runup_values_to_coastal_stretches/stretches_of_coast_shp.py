from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterFolderDestination,
    QgsProcessingMultiStepFeedback
)
import processing
import os


class ExportStretchToShapefile(QgsProcessingAlgorithm):

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

        self.addParameter(QgsProcessingParameterFolderDestination(
            'OUTPUT_FOLDER',
            'Cartella di output'
        ))

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)

        layer = self.parameterAsVectorLayer(parameters, 'INPUT', context)
        field_name = self.parameterAsString(parameters, 'FIELD', context)
        folder = self.parameterAsString(parameters, 'OUTPUT_FOLDER', context)

        # Crea cartella se non esiste
        if not os.path.exists(folder):
            os.makedirs(folder)

        # Recupero ID unici
        unique_ids = sorted(set([f[field_name] for f in layer.getFeatures()]))

        total = len(unique_ids)
        current = 0

        for uid in unique_ids:

            if feedback.isCanceled():
                break

            current += 1
            feedback.setProgress(int(current / total * 100))

            # Nome file sicuro
            uid_int = int(uid)
            out_path = os.path.join(folder, f"stretch_{uid_int}.shp")

            # Espressione filtro
            expr = f'"{field_name}" = {uid_int}'

            alg_params = {
                'INPUT': layer,
                'EXPRESSION': expr,
                'OUTPUT': out_path
            }

            processing.run(
                'native:extractbyexpression',
                alg_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )

        return {}

    def name(self):
        return 'export_stretch_to_shapefile'

    def displayName(self):
        return 'Export shapefile per stretch_ID'

    def group(self):
        return 'Custom scripts'

    def groupId(self):
        return 'customscripts'

    def createInstance(self):
        return ExportStretchToShapefile()