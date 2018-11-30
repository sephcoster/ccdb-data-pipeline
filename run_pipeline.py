import os
import configargparse
import logging
from elasticsearch import Elasticsearch
import complaints.ccdb.index_ccdb as ccdb_index
import complaints.taxonomy.index_taxonomy as taxonomy_index
from complaints.streamParser import parse_json

DOC_TYPE_NAME = 'complaint'


def build_arg_parser():
    p = configargparse.getArgumentParser(
        prog='run_pipeline',
        description='download complaints and index in Elasticsearch',
        ignore_unknown_config_file_keys=True,
        default_config_files=['./config.ini'],
        args_for_setting_config_path=['-c', '--config'],
        args_for_writing_out_config_file=['--save-config']
    )
    p.add('--dump-config', action='store_true', dest='dump_config',
          help='dump config vars and their source')
    p.add('--es-host', '-o', required=True, dest='es_host',
          help='Elasticsearch host', env_var='ES_HOST')
    p.add('--es-port', '-p', required=True, dest='es_port',
          help='Elasticsearch port', env_var='ES_PORT')
    p.add('--es-username', '-u', required=False, dest='es_username',
          default='',
          help='Elasticsearch username', env_var='ES_USERNAME')
    p.add('--es-password', '-a', required=False, dest='es_password',
          default='',
          help='Elasticsearch password', env_var='ES_PASSWORD')
    p.add('--index-name', '-i', required=True, dest='index_name',
          help='Elasticsearch index name')
    return p


def setup_complaint_logging(doc_type_name):
    logger = logging.getLogger(doc_type_name)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


def get_es_connection(config):
    url = "{}://{}:{}".format("http", config.es_host, config.es_port)
    es = Elasticsearch(
        url, http_auth=(config.es_username, config.es_password),
        user_ssl=True, timeout=1000
    )
    return es


def download_and_index(parser_args):
    global logger
    logger = setup_complaint_logging(DOC_TYPE_NAME)

    c = parser_args

    index_alias = c.index_name
    index_name = "{}-v1".format(index_alias)
    backup_index_name = "{}-v2".format(index_alias)

    logger.info("Creating Elasticsearch Connection")
    es = get_es_connection(c)

    output_file_name = 'complaints/ccdb/ccdb_output.json'
    input_file_name = 'https://data.consumerfinance.gov/api/views/s6ew-h6mp/rows.json'

    logger.info("Begin processing input")
    parse_json(input_file_name, output_file_name, logger)

    logger.info("Begin indexing data in Elasticsearch")
    ccdb_index.index_json_data(es, logger, DOC_TYPE_NAME,
                               'complaints/settings.json',
                               'complaints/ccdb/ccdb_mapping.json',
                               'complaints/ccdb/ccdb_output.json',
                               index_name, backup_index_name, index_alias)

def main():
    p = build_arg_parser()
    c = p.parse()

    if c.dump_config:
        print(p.format_values())

    download_and_index(c)

if __name__ == '__main__':
    main()
