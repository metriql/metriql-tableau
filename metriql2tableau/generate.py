import sys
from xml.etree.ElementTree import Element, tostring
import os
from .metadata import MetriqlMetadata
from tableaudocumentapi import Datasource

direct_mapping_types = ['boolean', 'integer', 'boolean', 'date']


class GenerateTDS:
    metadata: MetriqlMetadata

    def __init__(self, metadata: MetriqlMetadata) -> None:
        self.metadata = metadata

    def generate(self, dataset_name, output_file: str):
        dataset = self.metadata.get_dataset(dataset_name)
        source_tds = Datasource.from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'boilerplate.tds'))
        datasource_xml = source_tds._datasourceXML

        url = self.metadata.get_url()
        connection = source_tds.connections[0]
        connection.server = url.hostname
        connection.port = str(url.port or 80)

        relations = datasource_xml.findall('.//relation')
        for relation in relations:
            relation.set('name', dataset.get('name'))
            relation.set('table', "[{}].[{}]".format(dataset.get('category') if dataset.get('category') else "public",
                                                     dataset.get('name')))

        dimensions = self.metadata.get_dimensions(dataset.get('name'))
        measures = self.metadata.get_measures(dataset.get('name'))
        drill_paths = self.append_columns(dataset, datasource_xml, dimensions, measures)

        if len(drill_paths) > 0:
            # must be written just before the folders
            drill_paths_node = Element("drill-paths")
            for path in drill_paths:
                drill_paths_node.append(path)
            datasource_xml.append(drill_paths_node)

        self.append_folders(datasource_xml, dimensions, measures)

        field = Element("layout",
                        {"dim-ordering": "alphabetic", "dim-percentage": "0.5", "measure-ordering": "alphabetic",
                         "measure-percentage": "0.4", "show-structure": "false"})
        datasource_xml.append(field)

        self.indent(source_tds._datasourceXML)

        if output_file is not None:
            source_tds._datasourceTree.write(output_file, encoding="utf-8", xml_declaration=True)
        else:
            sys.stdout.buffer.write(str.encode("<?xml version='1.0' encoding='utf-8'?>\n"))
            sys.stdout.buffer.write(tostring(source_tds._datasourceTree._root))

    @staticmethod
    def _get_field_category(field, relation):
        category = field.get('category')
        if relation is not None:
            if category is not None:
                return "{} / {}".format(relation.get('label'), )
            else:
                return relation.get('label')
        elif category is not None:
            return category

    @staticmethod
    def append_folders(datasource_xml, dimensions, measures):
        dimension_folders = {}
        for name, (dimension, relation) in dimensions.items():
            category = GenerateTDS._get_field_category(dimension, relation)
            if category is not None:
                columns = dimension_folders.setdefault(category, [])
                columns.append(name)

        for name, columns in dimension_folders.items():
            datasource_xml.append(GenerateTDS._create_folder(name, 'dimensions', columns))

        measure_folders = {}
        for name, (measure, relation) in measures.items():
            category = GenerateTDS._get_field_category(measure, relation)
            if category is not None:
                names = measure_folders.setdefault(category, [])
                names.append(name)

        for name, columns in measure_folders.items():
            datasource_xml.append(GenerateTDS._create_folder(name, 'measures', columns))

    def append_columns(self, dataset, datasource_xml, dimensions, measures):
        drill_paths = []

        for name, (dimension, relation) in dimensions.items():
            post_operations = dimension.get('postOperations')
            if post_operations is None:
                self._append_column(dataset, datasource_xml, name, dimension, default_type="string")
            else:
                for post_operation in post_operations:
                    self._append_column(dataset, datasource_xml, name, dimension, post_operation=post_operation, default_type="string")
                drill_paths.append(
                    self._create_drill_path(name, map(lambda op: "{}::{}".format(name, op), post_operations)))

        for name, (measure, relation) in measures.items():
            measure_type = measure.get('type')
            measure_value = measure.get('value')
            aggregation = measure_value.get('aggregation')

            if measure_type == 'dimension':
                pass
            elif measure_type == 'column':
                if measure_value.get('column') is not None:
                    # check if there is such dimension
                    dimension_for_measure = self.metadata.get_dimension_for_column(dataset, measure_value.get('column'))
                    if dimension_for_measure is None:
                        self._append_column(dataset, datasource_xml, name, dimension,
                                            default_aggregation=aggregation, default_type="double")
                    else:
                        tableau_aggregation = self.convert_tableau_aggregation(aggregation)
                        # self._append_column(dataset, datasource_xml, name, measure,
                        #                     formula='{}({})'.format(tableau_aggregation, dimension_for_measure.get('name')), default_type="double")
                else:
                    self._append_column(dataset, datasource_xml, name,
                                        dimension, formula='1',
                                        extra={"user:auto-column": 'numrec'},  default_type="integer")
            elif measure_type == 'sql':
                self._append_column(dataset, datasource_xml, name, dimension,
                                    formula=measure_value.get('sql'), default_type="double")
            else:
                raise ValueError

        return drill_paths

    @staticmethod
    def indent(elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                GenerateTDS.indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    @staticmethod
    def _get_column_type(field_type, post_operation):
        if field_type in direct_mapping_types or post_operation is not None:
            return "ordinal"  # 1,2,3
        else:
            return "nominal"  # category

    @staticmethod
    def _get_column_datatype(field_type: str):
        if field_type is None:
            return None

        if field_type in ['timestamp', 'date', 'time']:
            return "string"

        if field_type in ['boolean', 'integer', 'boolean', 'string']:
            return field_type

        if field_type in ['double', 'long']:
            return 'real'

    @staticmethod
    def _convert_to_tableau_expression(expression):
        return expression

    def _append_column(self, dataset, datasource_xml, name, field, post_operation=None, default_aggregation=None,
                       formula=None, extra=None, default_type=None):
        name_reference = "{}::{}".format(name, post_operation) if post_operation is not None else name
        label = field.get('label') or name
        caption = post_operation if post_operation is not None else label

        is_measure = default_aggregation is not None or formula is not None
        if is_measure:
            tableau_type = "quantitative"
        else:
            tableau_type = GenerateTDS._get_column_type(field.get('fieldType'), post_operation)

        attrs = {"name": "[{}]".format(name_reference),
                 "caption": caption,
                 "role": "dimension" if not is_measure else "measure",
                 "default-role": "dimension" if formula is None else "measure",
                 "type": tableau_type}
        if extra is not None:
            attrs.update(extra)

        node = Element("column", attrs)
        datatype = GenerateTDS._get_column_datatype(field.get('fieldType'))
        if datatype is not None or default_type is not None:
            node.attrib["datatype"] = datatype if datatype is not None else GenerateTDS._get_column_datatype(default_type)

        if formula is not None:
            formula_node = Element('calculation',
                                   {"formula": GenerateTDS._convert_to_tableau_expression(formula), "class": "tableau"})
            node.append(formula_node)
        else:
            if len(field.get("description", '')) > 0:
                node.append(GenerateTDS._create_desc_node(field.get("description")))

        default_aggregation = default_aggregation or self.metadata.default_aggregation_for_dimension(dataset, field)
        if default_aggregation is not None and not is_measure:
            node.attrib['aggregation'] = self.convert_tableau_aggregation(default_aggregation)

        datasource_xml.append(node)

    @staticmethod
    def convert_tableau_aggregation(aggregation):
        if aggregation in ['count', 'sum']:
            return aggregation.capitalize()
        if aggregation in ['approximateUnique', 'countUnique']:
            return 'CountD'
        if aggregation == 'average':
            return 'Avg'
        if aggregation == 'minimum':
            return 'Min'
        if aggregation == 'maximum':
            return 'Max'
        if aggregation == 'sumDistinct':
            return 'Sum'
        if aggregation == 'averageDistinct':
            return 'Avg'
        else:
            raise Exception('Unknown aggregation {}'.format(aggregation))

    @staticmethod
    def _create_folder(name, role, columns):
        folder = Element('folder', {"name": name, "role": role})
        for column in columns:
            folder_item = Element("folder-item", {"name": '[{}]'.format(column), "type": "field"})
            folder.append(folder_item)
        return folder

    @staticmethod
    def _create_drill_path(name, columns):
        drill_path = Element('drill-path', {"name": name})
        for column in columns:
            field = Element("field")
            field.text = '[{}]'.format(column)
            drill_path.append(field)
        return drill_path

    @staticmethod
    def _create_desc_node(description):
        desc = Element('desc')
        formatted_text = Element("formatted-text")
        run = Element("run")
        run.text = description
        desc.append(formatted_text)
        formatted_text.append(run)
        return desc
