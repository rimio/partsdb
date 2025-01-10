import os
import argparse
import urllib3
import json

# https://sqlpey.com/python/solved-how-to-convert-any-string-to-a-valid-filename-using-python/
def sanitize_filename(s: str) -> str:
    return ''.join(c for c in s if c.isalnum() or c in "-_.() ")

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
    
    def default_filename(self):
        return '.database/{}.json'.format(sanitize_filename(self.partNum))

    def save(self, filename=None):
        if filename is None:
            filename = self.default_filename()
        with open(filename, 'w') as file:
            file.write(json.dumps(self.__dict__, indent=4))

    def to_string(self, index=None):
        out = ''
        if index is not None:
            out += '[ {:>2} ] '.format(index)
        out += '{}: {}'.format(self.partNum, self.description)
        return out

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
            
            parts.append(part)
        return parts

def lookup(query, api='mouser', exact=False, insert=False):
    config = Config()
    searcher = PartSearch.instantiate(api, config)
    result = searcher.search(query, exact)
    parser = PartParser.instantiate(api, config)
    parts = parser.parse(result)
    i = 1
    for p in parts:
        print(p.to_string(i))
        i += 1
    if insert:
        if len(parts) > 1:
            print('Refusing to insert more than one part, make your query more selective!')
        elif len(parts) == 0:
            print('No parts were found, nothing to insert!')
        else:
            parts[0].save()

def inventory(api='mouser'):
    config = Config()
    searcher = PartSearch.instantiate(api, config)
    while True:
        partid = input('Part ID (or \'q\' to exit): ')
        if partid == 'q':
            break
        result = searcher.search(partid, False)
        parser = PartParser.instantiate(api, config)
        parts = parser.parse(result)
        
        if len(parts) == 0:
            print('Found no parts for this keyword ...')
            continue
        elif len(parts) == 1:
            part = parts[0]
        elif len(parts) > 1:
            print('Found multiple parts for this keyword:')
            i = 1
            for p in parts:
                print(p.to_string(i))
                i += 1
            sel = 0
            while sel < 1 or sel > len(parts):
                which = input('Select part to add (or \'q\' to exit): ')
                if which == 'q':
                    sel = None
                    break
                try:
                    sel = int(which)
                except Exception as e:
                    print('Selection error: {}'.format(e))
            if sel == None:
                continue
            part = parts[sel - 1]
        
        print('\nSelected part:\n{}\n'.format(part.to_string()))
        count = 0
        while count < 1:
            try:
                count = input('Count (or \'q\' to exit): ')
                if count == 'q':
                    count = None
                    break
                count = int(count)
            except:
                print('Conversion error: {}'.format(e))
        part.count = count

        part.save()
        print('Written part to \'{}\' ...\n\n'.format(part.default_filename()))


def main():
    # argument parsing
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', help='subcommand')
    parser_lookup = subparsers.add_parser('lookup', help='look up part online')
    parser_lookup.add_argument('query', help='query string', type=str)
    parser_lookup.add_argument('-a', '--api', help='API to use', type=str, default='mouser')
    parser_lookup.add_argument('-e', '--exact', help='query string is exact manufacturer ID', action='store_true')
    parser_lookup.add_argument('-i', '--insert', help='insert into database', action='store_true')
    parser_inventory = subparsers.add_parser('inventory', help='inventory mode, insert multiple parts into database with TUI')
    parser_inventory.add_argument('-a', '--api', help='API to use', type=str, default='mouser')
    arguments = parser.parse_args()

    # execute command
    if arguments.command is None:
        print('Command not specified!')
        parser.print_usage()
        return

    if arguments.command == 'lookup':
        lookup(arguments.query, api=arguments.api, exact=arguments.exact, insert=arguments.insert)
    elif arguments.command == 'inventory':
        inventory(arguments.api)
    else:
        raise RuntimeError('unhandled command {}'.format(arguments.command))

if __name__ == '__main__':
    main()
