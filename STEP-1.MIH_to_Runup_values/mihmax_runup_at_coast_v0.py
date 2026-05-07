from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterField,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsSpatialIndex
)
from PyQt5.QtCore import QVariant
import processing


class MihAtCoast(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                'neamthm18',
                'NEAMTHM18 points',
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                'MIH_field',
                'MIH field',
                parentLayerParameterName='neamthm18',
                type=QgsProcessingParameterField.Numeric
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                'shoreline',
                'Coastline',
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                'Points_distance',
                'Distance between coast points (m)',
                QgsProcessingParameterNumber.Double,
                defaultValue=2000
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                'Search_radius',
                'Search radius (m)',
                QgsProcessingParameterNumber.Double,
                defaultValue=40000
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                'Amplification_factor',
                'Amplification factor',
                QgsProcessingParameterNumber.Double,
                defaultValue=1.0
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                'OUTPUT',
                'Output'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        mih_source = self.parameterAsSource(parameters, 'neamthm18', context)
        shoreline_layer = self.parameterAsVectorLayer(parameters, 'shoreline', context)

        mih_field = self.parameterAsString(parameters, 'MIH_field', context)
        radius = self.parameterAsDouble(parameters, 'Search_radius', context)
        amp = self.parameterAsDouble(parameters, 'Amplification_factor', context)
        distance = self.parameterAsDouble(parameters, 'Points_distance', context)

        # 1 punti lungo costa
        points_result = processing.run(
            "native:pointsalonglines",
            {
                'INPUT': shoreline_layer,
                'DISTANCE': distance,
                'START_OFFSET': 0,
                'END_OFFSET': 0,
                'OUTPUT': 'memory:'
            },
            context=context,
            feedback=feedback
        )

        coast_points = points_result['OUTPUT']

        # 2 indice spaziale MIH
        index = QgsSpatialIndex()
        mih_features = {}

        for f in mih_source.getFeatures():
            index.insertFeature(f)
            mih_features[f.id()] = f

        # 3 campi output
        fields = QgsFields()
        fields.append(QgsField("MIHmax", QVariant.Double))
        fields.append(QgsField("RunUp", QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            'OUTPUT',
            context,
            fields,
            coast_points.wkbType(),
            coast_points.sourceCrs()
        )

        total = coast_points.featureCount()

        for i, pt in enumerate(coast_points.getFeatures()):

            geom = pt.geometry()
            buffer_geom = geom.buffer(radius, 8)

            ids = index.intersects(buffer_geom.boundingBox())

            max_mih = None

            for fid in ids:
                f = mih_features[fid]

                if buffer_geom.contains(f.geometry()):

                    val = f[mih_field]

                    if val is not None:
                        if max_mih is None or val > max_mih:
                            max_mih = val

            runup = None
            if max_mih is not None:
                runup = max_mih * amp

            new_feat = QgsFeature()
            new_feat.setGeometry(geom)
            new_feat.setFields(fields)

            new_feat["MIHmax"] = max_mih
            new_feat["RunUp"] = runup

            sink.addFeature(new_feat)

            feedback.setProgress(int(i / total * 100))

        return {'OUTPUT': dest_id}

    def name(self):
        return 'mih_at_coast'

    def displayName(self):
        return 'MIH at coast (max within radius)'

    def group(self):
        return 'MIH analysis'

    def groupId(self):
        return 'mih_analysis'

    def createInstance(self):
        return MihAtCoast()