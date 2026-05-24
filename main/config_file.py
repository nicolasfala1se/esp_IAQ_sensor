  # Copyright 2017 Gautier HUSSON - Liberasys

# The MIT License (MIT)
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

try:
    import ujson as json
except ImportError:
    try:
        import json
    except ImportError:
        print("No json library not found.")
        raise SystemExit


class jsonfile:
    ''' This class loads and stores a data from and to a file with json formalism.'''

    def __init__(self, file_path, default_data = {}):
        ''' mandatory argument : file path
            optional argument : default data
              if none provided, an empty dictionnary is set'''

        self.file_path = file_path
        self.data = default_data
        self.load_file()


    def load_file(self):
        ''' Returns the data loaded from json file, or the default one '''

        try:
            with open(self.file_path) as json_file:
                data_from_file = json.loads(json_file.read())
        
        except (OSError, ValueError):
            print("Couldn't load " + self.file_path + ". Creating a default one.")
            self.store_data()
        
        else:
            if type(self.data) is dict and type(data_from_file) is dict:
                self.data.update(data_from_file)
            else:
                self.data = data_from_file
            print("Loaded config from " + self.file_path + ".")
            json_file.close()


    def get_data(self):
        ''' Returns the data '''
        return(self.data)


    def set_data(self, new_data):
        ''' Stores the data in the instance '''
        self.data = new_data


    def update_data_dict(self, dict_to_be_merged):
        ''' Merges the dictionnary given in argument with self data dictionnary '''
        if type(self.data) is dict and type(dict_to_be_merged) is dict:
            self.data.update(dict_to_be_merged)
        else:
            print("Trying to update dictionnary, but non dict found.")
            raise SystemExit


    def store_data(self):
        ''' Saves the data to json file.'''
        try:
            with open(self.file_path, "w") as json_file:
                json_file.write(json.dumps(self.data))
        except OSError:
            print("Couldn't save " + self.file_path + ".")


#===============================================================================
# if __name__ == "__main__":
#     my_jsonfile = jsonfile("./test.json", default_data = {"a": "porty", "b": "portx"})
#     print(my_jsonfile.get_data())
#     update_data = {"c": "portc", "b": "portb"}
#     my_jsonfile.update_data_dict(update_data)
#     print(my_jsonfile.get_data())
#     my_jsonfile.store_data()
#===============================================================================




