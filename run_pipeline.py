import os
import configargparse
import logging
from elasticsearch import Elasticsearch
import complaints.ccdb.index_ccdb as ccdb_index
import complaints.taxonomy.index_taxonomy as taxonomy_index
from complaints.streamParser import parse_json

DOC_TYPE_NAME = 'complaint'

def build_arg_parser():
    p = configargparse.ArgParser(prog='run_pipeline',
                                 description='download complaints and index in Elasticsearch',
                                 ignore_unknown_config_file_keys=True)
    p.add('-c', '--my-config', required=False, is_config_file=True,
        help='config file path')
    p.add('--es-host', '-o', required=True, dest='es_host',
        help='Elasticsearch host', env_var='ES_HOST')
    p.add('--es-port', '-p', required=True, dest='es_port',
        help='Elasticsearch port', env_var='ES_PORT')
    p.add('--es-username', '-u', required=False, dest='es_username',
        help='Elasticsearch username', env_var='ES_USERNAME')
    p.add('--es-password', '-a', required=False, dest='es_password',
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


def get_es_connection():
    url = "{}://{}:{}".format("http", os.getenv('ES_HOST', ''), os.getenv('ES_PORT', ''))
    es = Elasticsearch(url, http_auth=(os.getenv('ES_USERNAME', ''), os.getenv('ES_PASSWORD', '')), user_ssl=True, timeout=1000)
    return es

def test_index_growing(es, index_name):
    ''' count index and make sure that number is stable or growing '''
    filename='count_data_' + index_name + '-' + DOC_TYPE_NAME + '.txt'
    res = es.search(index=index_name, doc_type=DOC_TYPE_NAME)
    hits_count = res['hits']['total']
    assert 'hits' in res
    try:
        with open(filename, 'r') as f:
            prev_total = int(f.read())
    except:
        prev_total = 0
        logger.info("count file did not exist")
    logger.info("%s >= %d" % (hits_count, prev_total))
    assert hits_count >= prev_total
    with open(filename, 'w+') as f:
        f.write(str(hits_count))
    logger.info("Count written to file")


def download_and_index(parser_args):
    global logger
    logger = setup_complaint_logging(DOC_TYPE_NAME)

    c = parser_args

    os.environ["ES_HOST"] = c.es_host
    os.environ["ES_PORT"] = c.es_port
    os.environ["ES_USERNAME"] = c.es_username or ''
    os.environ["ES_PASSWORD"] = c.es_password or ''

    index_alias = c.index_name
    index_name = "{}-v1".format(index_alias)
    backup_index_name = "{}-v2".format(index_alias)

    logger.info("Creating Elasticsearch Connection")
    es = get_es_connection()

    logger.info("Testing to ensure Socrata index is stable or growing")
    test_index_growing(es, index_name)

    output_file_name = 'complaints/ccdb/ccdb_output.json'
    input_file_name = 'https://data.consumerfinance.gov/api/views/s6ew-h6mp/rows.json'

    logger.info("Begin processing input")
    parse_json(input_file_name, output_file_name, logger)

    logger.info("Begin indexing data in Elasticsearch")
    ccdb_index.index_json_data(es, logger, DOC_TYPE_NAME, 'complaints/settings.json', 'complaints/ccdb/ccdb_mapping.json', \
      'complaints/ccdb/ccdb_output.json', index_name, backup_index_name, index_alias)

    taxonomy_index.index_taxonomy(es, logger, 'complaints/taxonomy/taxonomy.txt', index_alias)

def main():
    p = build_arg_parser()
    c = p.parse_args()
    download_and_index(c)

if __name__ == '__main__':
    main()
