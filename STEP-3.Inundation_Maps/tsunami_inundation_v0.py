from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsProcessingParameterVectorDestination
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsProcessingParameterFolderDestination
from qgis.core import QgsVectorLayer
from qgis.core import QgsProject
import processing
import os

class Tsunami_test_inundation_rivers_lakes_list(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        # Aggiungi i parametri
        self.addParameter(QgsProcessingParameterRasterLayer('digital_terrain_model', 'Digital Terrain Model', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('river_network', 'River Network', types=[QgsProcessing.TypeVectorAnyGeometry], defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterString('text_runup_values', 'Insert the list of runup values separated by semicolon', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('shoreline', 'Shoreline', types=[QgsProcessing.TypeVectorAnyGeometry], defaultValue=None))
        self.addParameter(QgsProcessingParameterFolderDestination('output_folder', 'Output Folder', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('lakes', 'Lakes', types=[QgsProcessing.TypeVectorAnyGeometry], defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterVectorDestination('wet_dry_area_vector', 'Wet/Dry Area Vector', type=QgsProcessing.TypeVectorPolygon, createByDefault=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('wet_dry_area_raster', 'Wet/Dry Area Raster', createByDefault=True, defaultValue=''))
        self.addParameter(QgsProcessingParameterVectorDestination('wet_area_vector', 'Wet Area Vector', type=QgsProcessing.TypeVectorPolygon, createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(12, model_feedback)
        results = {}
        outputs = {}
        list_runup_values = parameters['text_runup_values'].split(";")
        
        for i in range(0, len(list_runup_values)):
            # Sostituire la virgola con il punto per gestire i valori decimali
            runup_text = list_runup_values[i].replace(",", ".")
            
            # Esegui la conversione in float
            runup_value = float(runup_text)
            
            # Nome del file basato sul valore di runup
            runup_text_for_filename = runup_text.replace(".", ",")
            
            # 1. Buffer per la costa in base al moltiplicatore di runup
            if parameters['shoreline'] is not None:
                buffer_distance = 200 * runup_value
                alg_params = {
                    'DISSOLVE': True,
                    'DISTANCE': buffer_distance,
                    'INPUT': parameters['shoreline'],
                    'END_CAP_STYLE': 0,
                    'JOIN_STYLE': 0,
                    'MITER_LIMIT': 2,
                    'SEGMENTS': 5,
                    'SEPARATE_DISJOINT': False,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['Buffer_coast'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}

            # 2. Buffer per i laghi
            if parameters['lakes'] is not None:
                buffer_distance = 200 * runup_value
                alg_params = {
                    'DISSOLVE': True,
                    'DISTANCE': buffer_distance,
                    'INPUT': parameters['lakes'],
                    'END_CAP_STYLE': 0,
                    'JOIN_STYLE': 0,
                    'MITER_LIMIT': 2,
                    'SEGMENTS': 5,
                    'SEPARATE_DISJOINT': False,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['Buffer_lakes'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}

            # 3. Buffer per la costa da usare per ritagliare i fiumi
            if parameters['shoreline'] is not None:
                buffer_distance = 400 * runup_value
                alg_params = {
                    'DISSOLVE': True,
                    'DISTANCE': buffer_distance,
                    'INPUT': parameters['shoreline'],
                    'END_CAP_STYLE': 0,
                    'JOIN_STYLE': 0,
                    'MITER_LIMIT': 2,
                    'SEGMENTS': 5,
                    'SEPARATE_DISJOINT': False,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['Bf_coastToClipRivers'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}

            # 4. Ritaglia la rete fluviale usando il buffer dalla costa (se la rete fluviale è fornita)
            if parameters['river_network'] is not None:
                alg_params = {
                    'INPUT': parameters['river_network'],
                    'OVERLAY': outputs['Bf_coastToClipRivers']['OUTPUT'],
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['Clip_riversByBfCoast'] = processing.run('native:clip', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}
            else:
                outputs['Clip_riversByBfCoast'] = None

            # 5. Buffer per i fiumi ritagliati (se esistono)
            if outputs['Clip_riversByBfCoast'] is not None:
                buffer_distance = runup_value * 100
                alg_params = {
                    'DISSOLVE': True,
                    'DISTANCE': buffer_distance,
                    'INPUT': outputs['Clip_riversByBfCoast']['OUTPUT'],
                    'END_CAP_STYLE': 0,
                    'JOIN_STYLE': 0,
                    'MITER_LIMIT': 2,
                    'SEGMENTS': 5,
                    'SEPARATE_DISJOINT': False,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['Buffer_rivers'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}
            else:
                outputs['Buffer_rivers'] = None

            # 6. Unione dei buffer (solo se esistono entrambi)
            layers_to_merge = []
            if outputs.get('Buffer_coast') is not None:
                layers_to_merge.append(outputs['Buffer_coast']['OUTPUT'])
            if outputs.get('Buffer_rivers') is not None:
                layers_to_merge.append(outputs['Buffer_rivers']['OUTPUT'])
            if outputs.get('Buffer_lakes') is not None:
                layers_to_merge.append(outputs['Buffer_lakes']['OUTPUT'])
            
            if layers_to_merge:
                alg_params = {
                    'CRS': None,
                    'LAYERS': layers_to_merge,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['Merge_buffers'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}

            # 7. Dissolvi i buffer uniti
            if outputs.get('Merge_buffers') is not None:
                alg_params = {
                    'FIELD': [],
                    'INPUT': outputs['Merge_buffers']['OUTPUT'],
                    'SEPARATE_DISJOINT': False,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['Dissolve_merged_bf'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}

            # 8. Ritaglia il raster usando il buffer dissolto
            if outputs.get('Dissolve_merged_bf') is not None:
                alg_params = {
                    'ALPHA_BAND': False,
                    'CROP_TO_CUTLINE': True,
                    'DATA_TYPE': 0,
                    'INPUT': parameters['digital_terrain_model'],
                    'MASK': outputs['Dissolve_merged_bf']['OUTPUT'],
                    'MULTITHREADING': False,
                    'NODATA': None,
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['ClipRasterByMaskLayer'] = processing.run('gdal:cliprasterbymasklayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}

            # 9. Calcola l'area wet/dry
            if outputs.get('ClipRasterByMaskLayer') is not None:
                alg_params = {
                    'CELL_SIZE': None,
                    'CRS': 'ProjectCrs',
                    'EXPRESSION': f'"A@1" <= {runup_value}',
                    'EXTENT': None,
                    'LAYERS': outputs['ClipRasterByMaskLayer']['OUTPUT'],
                    'OUTPUT': parameters['wet_dry_area_raster']
                }
                outputs['Calc_wet_dry'] = processing.run('native:modelerrastercalc', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

                if feedback.isCanceled():
                    return {}

            # 10. Polygonizza il raster (converti in vettore)
            if outputs.get('Calc_wet_dry') is not None:
                alg_params = {
                    'BAND': 1,
                    'EIGHT_CONNECTEDNESS': True,
                    'EXTRA': None,
                    'FIELD': 'wet_dry',
                    'INPUT': outputs['Calc_wet_dry']['OUTPUT'],
                    'OUTPUT': parameters['wet_dry_area_vector']
                }
                outputs['PolygonizeRasterToVector'] = processing.run('gdal:polygonize', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            # 11. Filtra solo le aree bagnate (wet_dry = 1)
            if outputs.get('PolygonizeRasterToVector') is not None:
                alg_params = {
                    'INPUT': outputs['PolygonizeRasterToVector']['OUTPUT'],
                    'EXPRESSION': '"wet_dry" = 1',
                    'OUTPUT': parameters['wet_area_vector']
                }
                outputs['FilteredWetArea'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            # 12. Salvataggio dell'area wet e wet/dry
            if outputs.get('FilteredWetArea') is not None:
                runup_text_for_filename = str(runup_value).replace('.', ',')
                saving_path_wet = os.path.join(parameters['output_folder'], f'wet_area_{runup_text_for_filename}.shp')

                alg_params = {
                    'INPUT': outputs['FilteredWetArea']['OUTPUT'],
                    'OUTPUT': saving_path_wet
                }
                outputs['Save_wet_area'] = processing.run('native:savefeatures', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            # Salvataggio dell'area wet/dry
            if outputs.get('PolygonizeRasterToVector') is not None:
                saving_path_wetdry = os.path.join(parameters['output_folder'], f'area_wetdry_{runup_text_for_filename}.shp')

                alg_params = {
                    'INPUT': outputs['PolygonizeRasterToVector']['OUTPUT'],
                    'OUTPUT': saving_path_wetdry
                }
                outputs['Save_wetdry_area'] = processing.run('native:savefeatures', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            # Salvataggio del raster per l'area wet/dry
            if outputs.get('Calc_wet_dry') is not None:
                saving_path_wetdry_raster = os.path.join(parameters['output_folder'], f'area_wetdry_{runup_text_for_filename}.tif')
                alg_params = {
                    'INPUT': outputs['Calc_wet_dry']['OUTPUT'],
                    'OUTPUT': saving_path_wetdry_raster
                }
                outputs['Save_wet_dry_area_raster'] = processing.run('gdal:translate', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        return {
            'wet_area_vector': saving_path_wet,
            'wet_dry_area_raster': saving_path_wetdry_raster
        }

    def name(self):
        return 'tsunami_test_inundation_rivers_lakes_list'

    def displayName(self):
        return 'Tsunami Inundation'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return Tsunami_test_inundation_rivers_lakes_list()
