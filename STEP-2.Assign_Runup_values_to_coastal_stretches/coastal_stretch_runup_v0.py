from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterFeatureSink
import processing


class StretchOfCoast(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        # Input
        self.addParameter(QgsProcessingParameterNumber(
            'distance_m2',
            'Point distance (m)',
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=1000
        ))

        self.addParameter(QgsProcessingParameterVectorLayer(
            'point_runup',
            'point_runup (shp)',
            types=[QgsProcessing.TypeVectorPoint]
        ))

        self.addParameter(QgsProcessingParameterField(
            'runup',
            'run-up (field)',
            type=QgsProcessingParameterField.Numeric,
            parentLayerParameterName='point_runup',
            allowMultiple=True
        ))

        self.addParameter(QgsProcessingParameterVectorLayer(
            'shoreline',
            'shoreline (shp)',
            types=[QgsProcessing.TypeVectorLine]
        ))

        # Output finale
        self.addParameter(QgsProcessingParameterFeatureSink(
            'StretchesOfCoast',
            'stretches of coast',
            type=QgsProcessing.TypeVectorAnyGeometry,
            createByDefault=True
        ))

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(5, model_feedback)
        results = {}
        outputs = {}

        # 1️⃣ Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': parameters['distance_m2'] / 2,
            'END_CAP_STYLE': 0,
            'INPUT': parameters['point_runup'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'SEPARATE_DISJOINT': False,
            'OUTPUT': 'memory:buffer_tmp'
        }
        outputs['Buffer'] = processing.run(
            'native:buffer',
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # 2️⃣ Dissolve
        dissolve_field = parameters['runup'][0] if isinstance(parameters['runup'], list) else parameters['runup']

        alg_params = {
            'FIELD': dissolve_field,
            'INPUT': outputs['Buffer']['OUTPUT'],
            'SEPARATE_DISJOINT': False,
            'OUTPUT': 'memory:dissolve_tmp'
        }
        outputs['Dissolve'] = processing.run(
            'native:dissolve',
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # 3️⃣ Multi-intersection
        alg_params = {
            'INPUT': parameters['shoreline'],
            'OVERLAYS': [outputs['Dissolve']['OUTPUT']],
            'OVERLAY_FIELDS_PREFIX': None,
            'OUTPUT': 'memory:intersection_tmp'
        }
        outputs['Intersection'] = processing.run(
            'native:multiintersection',
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # 4️⃣ Aggiunta campo run_up (intero)
        alg_params = {
            'FIELD_NAME': 'run_up',
            'FIELD_TYPE': 1,  # Integer
            'FIELD_LENGTH': 10,
            'FIELD_PRECISION': 0,
            'FORMULA': f'to_int("{dissolve_field}")',
            'INPUT': outputs['Intersection']['OUTPUT'],
            'OUTPUT': 'memory:runup_tmp'
        }
        outputs['RunUpField'] = processing.run(
            'native:fieldcalculator',
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # 5️⃣ Aggiunta ID progressivo
        alg_params = {
            'FIELD_NAME': 'stretch_ID',
            'GROUP_FIELDS': [],
            'INPUT': outputs['RunUpField']['OUTPUT'],
            'MODULUS': 0,
            'SORT_ASCENDING': True,
            'SORT_EXPRESSION': '',
            'SORT_NULLS_FIRST': False,
            'START': 1,
            'OUTPUT': parameters['StretchesOfCoast']
        }
        outputs['AddID'] = processing.run(
            'native:addautoincrementalfield',
            alg_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )

        results['StretchesOfCoast'] = outputs['AddID']['OUTPUT']

        return results

    def name(self):
        return 'stretch_of_coast'

    def displayName(self):
        return 'Stretch of Coast'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return StretchOfCoast()