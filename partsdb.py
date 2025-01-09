import os
import argparse
import urllib3
import json

class Config:
    def __init__(self):
        pass

    def mouser_api_key(self):
        if 'MOUSER_API_KEY' in os.environ.keys():
            return os.environ['MOUSER_API_KEY']
        raise RuntimeError('Mouser API key not provided')

class Part:
    def __init__(self, partNum):
        self.partNum = partNum

        self.category = 'uncategorized'
        self.manufacturer = 'unknown'
        self.description = None

        self.imageUrl = None
        self.datasheetUrl = None
        self.productUrl = None
        
        self.count = 0

    def save(self, filename=None):
        if filename is None:
            filename = '{}.json'.format(self.partNum)
        with open(filename, 'w') as file:
            file.write(json.dumps(self.__dict__, indent=4))

class PartSearch:
    def instantiate(api, config):
        if str.lower(api) == 'mouser':
            return MouserPartSearch(config)
        else:
            raise RuntimeError('unsupported API {}'.format(api))

    def __init__(self, config):
        raise NotImplementedError('cannot instantiate base class')

    def search(self, query, exact):
        raise NotImplementedError()

class MouserPartSearch(PartSearch):
    def __init__(self, config):
        self.api_key = config.mouser_api_key()
    
    def search(self, query, exact):
        http = urllib3.PoolManager()
        encoded_body = json.dumps({
                'SearchByKeywordRequest': {
                    'keyword': query,
                    'records': 25,
                    'startingRecord': 0
                 }
            }).encode('utf-8')
        response = http.request(
            'POST',
            'https://api.mouser.com/api/v1/search/keyword?apiKey={}'.format(self.api_key),
            headers={'Content-Type': 'application/json'},
            body=encoded_body)
        return json.loads(response.data.decode('utf-8'))

class PartParser:
    def instantiate(api, config):
        if str.lower(api) == 'mouser':
            return MouserPartParser(config)
        else:
            raise RuntimeError('unsupported API {}'.format(api))

    def __init__(self, config):
        raise NotImplementedError('cannot instantiate base class')

    def parse(self, obj):
        raise NotImplementedError()

class MouserPartParser:
    def __init__(self, config):
        self.api_key = config.mouser_api_key()

    def parse(self, obj):
        parts = []
        results = obj['SearchResults']
        for jpart in results['Parts']:
            part = Part(jpart['ManufacturerPartNumber'])
            part.category = jpart['Category'] or part.category
            part.manufacturer = jpart['Manufacturer'] or part.manufacturer
            part.description = jpart['Description'] or part.description

            part.imageUrl = jpart['ImagePath'] or part.datasheetUrl
            part.datasheetUrl = jpart['DataSheetUrl'] or part.datasheetUrl
            part.productUrl = jpart['ProductDetailUrl'] or part.productUrl
            part.save()
            
            parts.append(part)
        return parts

def lookup(query, api='mouser', exact=False):
    config = Config()
    searcher = PartSearch.instantiate(api, config)
    result = searcher.search(query, exact)
    parser = PartParser.instantiate(api, config)
    parts = parser.parse(result)
    for p in parts:
        print(json.dumps(p.__dict__))

def main():
    # argument parsing
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', help='subcommand')
    parser_lookup = subparsers.add_parser('lookup', help='look up part online')
    parser_lookup.add_argument('query', help='query string', type=str)
    parser_lookup.add_argument('-a', '--api', help='API to use', type=str, default='mouser')
    parser_lookup.add_argument('-e', '--exact', help='query string is exact manufacturer ID', action='store_true')
    parser_lookup.add_argument('-i', '--insert', help='insert into database', action='store_true')
    arguments = parser.parse_args()

    # execute command
    if arguments.command is None:
        print('Command not specified!')
        parser.print_usage()
        return

    if arguments.command == 'lookup':
        lookup(arguments.query, api=arguments.api, exact=arguments.exact)
    else:
        raise RuntimeError('unhandled command {}'.format(arguments.command))

if __name__ == '__main__':
    main()
