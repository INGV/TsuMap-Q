from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterFolderDestination,
    QgsVectorLayer,
    QgsProject
)
import processing
import os

class Tsunami_test_inundation_rivers_lakes_list(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer('digital_terrain_model', 'Digital Terrain Model'))
        self.addParameter(QgsProcessingParameterString('text_runup_values', 'Insert the list of runup values separated by semicolon'))
        self.addParameter(QgsProcessingParameterVectorLayer('shoreline', 'Shoreline', types=[QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterVectorLayer('river_network', 'River Network', types=[QgsProcessing.TypeVectorAnyGeometry], optional=True))
        self.addParameter(QgsProcessingParameterFolderDestination('output_folder', 'Output Folder'))
        self.addParameter(QgsProcessingParameterVectorLayer('lakes', 'Lakes', types=[QgsProcessing.TypeVectorAnyGeometry], optional=True))
        
    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(12, model_feedback)
        outputs = {}

        list_runup_values = parameters['text_runup_values'].split(";")
        last_saving_path_wet = ""

        # Recupera il valore di POI_ID dalla prima feature della shoreline
        shoreline_layer = self.parameterAsVectorLayer(parameters, 'shoreline', context)
        stretch_ID_value = None
        if shoreline_layer and shoreline_layer.featureCount() > 0:
            feature = next(shoreline_layer.getFeatures())
            stretch_ID_value = str(int(feature['stretch_ID']))  # Assicurati che 'POI_ID' sia il campo corretto
        else:
            raise Exception("Errore: il layer della shoreline non contiene feature o è nullo.")

        for runup_text in list_runup_values:
            runup_text = runup_text.replace(",", ".")
            runup_value = float(runup_text)
            runup_text_for_filename = runup_text.replace(".", ",")

            outputs['Buffer_coast'] = processing.run('native:buffer', {
                'DISSOLVE': True,
                'DISTANCE': 200 * runup_value,
                'INPUT': parameters['shoreline'],
                'END_CAP_STYLE': 0,
                'JOIN_STYLE': 0,
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'SEPARATE_DISJOINT': False,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)

            if parameters.get('lakes'):
                outputs['Buffer_lakes'] = processing.run('native:buffer', {
                    'DISSOLVE': True,
                    'DISTANCE': 200 * runup_value,
                    'INPUT': parameters['lakes'],
                    'END_CAP_STYLE': 0,
                    'JOIN_STYLE': 0,
                    'MITER_LIMIT': 2,
                    'SEGMENTS': 5,
                    'SEPARATE_DISJOINT': False,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }, context=context, feedback=feedback, is_child_algorithm=True)

            outputs['Bf_coastToClipRivers'] = processing.run('native:buffer', {
                'DISSOLVE': True,
                'DISTANCE': 400 * runup_value,
                'INPUT': parameters['shoreline'],
                'END_CAP_STYLE': 0,
                'JOIN_STYLE': 0,
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'SEPARATE_DISJOINT': False,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)

            if parameters.get('river_network'):
                outputs['Clip_riversByBfCoast'] = processing.run('native:clip', {
                    'INPUT': parameters['river_network'],
                    'OVERLAY': outputs['Bf_coastToClipRivers']['OUTPUT'],
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }, context=context, feedback=feedback, is_child_algorithm=True)

                outputs['Buffer_rivers'] = processing.run('native:buffer', {
                    'DISSOLVE': True,
                    'DISTANCE': 100 * runup_value,
                    'INPUT': outputs['Clip_riversByBfCoast']['OUTPUT'],
                    'END_CAP_STYLE': 0,
                    'JOIN_STYLE': 0,
                    'MITER_LIMIT': 2,
                    'SEGMENTS': 5,
                    'SEPARATE_DISJOINT': False,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }, context=context, feedback=feedback, is_child_algorithm=True)

            layers_to_merge = [outputs['Buffer_coast']['OUTPUT']]
            if 'Buffer_rivers' in outputs:
                layers_to_merge.append(outputs['Buffer_rivers']['OUTPUT'])
            if 'Buffer_lakes' in outputs:
                layers_to_merge.append(outputs['Buffer_lakes']['OUTPUT'])

            outputs['Merge_buffers'] = processing.run('native:mergevectorlayers', {
                'CRS': None,
                'LAYERS': layers_to_merge,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)

            outputs['Dissolve_merged_bf'] = processing.run('native:dissolve', {
                'FIELD': [],
                'INPUT': outputs['Merge_buffers']['OUTPUT'],
                'SEPARATE_DISJOINT': False,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)

            outputs['ClipRasterByMaskLayer'] = processing.run('gdal:cliprasterbymasklayer', {
                'ALPHA_BAND': False,
                'CROP_TO_CUTLINE': True,
                'DATA_TYPE': 0,
                'INPUT': parameters['digital_terrain_model'],
                'MASK': outputs['Dissolve_merged_bf']['OUTPUT'],
                'MULTITHREADING': False,
                'NODATA': None,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)

            outputs['Calc_wet_dry'] = processing.run('native:modelerrastercalc', {
                'CELL_SIZE': None,
                'CRS': 'ProjectCrs',
                'EXPRESSION': f'"A@1" <= {runup_value}',
                'EXTENT': None,
                'LAYERS': outputs['ClipRasterByMaskLayer']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)

            outputs['PolygonizeRasterToVector'] = processing.run('gdal:polygonize', {
                'BAND': 1,
                'EIGHT_CONNECTEDNESS': True,
                'EXTRA': None,
                'FIELD': 'wet_dry',
                'INPUT': outputs['Calc_wet_dry']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)

            outputs['FilteredWetArea'] = processing.run('native:extractbyexpression', {
                'INPUT': outputs['PolygonizeRasterToVector']['OUTPUT'],
                'EXPRESSION': '"wet_dry" = 1',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)

            # Qui usiamo il POI_ID per il nome del file
            saving_path_wet = os.path.join(parameters['output_folder'], f'wet_area_{stretch_ID_value}.shp')

            # Se vuoi includere ANCHE il runup nel nome:
            # saving_path_wet = os.path.join(parameters['output_folder'], f'wet_area_{stretch_ID_value}_runup_{runup_text_for_filename}.shp')

            last_saving_path_wet = saving_path_wet

            processing.run('native:savefeatures', {
                'INPUT': outputs['FilteredWetArea']['OUTPUT'],
                'OUTPUT': saving_path_wet
            }, context=context, feedback=feedback, is_child_algorithm=True)

            wet_layer = QgsVectorLayer(saving_path_wet, f"Wet_Area_{stretch_ID_value}", "ogr")
            if wet_layer.isValid():
                QgsProject.instance().addMapLayer(wet_layer)
            else:
                feedback.reportError(f"Errore: Impossibile caricare il layer da {saving_path_wet}")

        return {
            'wet_area_vector': last_saving_path_wet
        }

    def name(self):
        return 'tsunami_test_inundation_rivers_lakes_list'

    def displayName(self):
        return 'Tsunami Inundation'

    def group(self):
        return 'Tsunami Analysis'

    def groupId(self):
        return 'tsunami_analysis'

    def createInstance(self):
        return Tsunami_test_inundation_rivers_lakes_list()
