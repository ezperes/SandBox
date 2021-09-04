""" Dream Company Ecosystem: Agents: Identification Handler Module """

import pandas as pd
import numpy as np


class IdHandler:
    """ Dream Company Ecosystem: Agents: Identification Handler

        PURPOSE
            To centralize, discipline and manage the states (attributes) and
            behavior (methods) of
                1. Generation
                2. Allocation
                3. Translation
            of IDENTIFICATORS of SPAWNED AGENTS within DreamEco

        FUNCTIONALITY MECHANISM
            1. Identificator is a 64 bit integer which identifies the *nature* of the agent and its serial number
                i.  The 6 initial bits represents *nature*
                ii. The 58 other bits represents the serial number

                Visual representation:
                            |
                    nnnnnn  |  mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm
                            |
                    6 bits  |                       58  bits
                nature code |                   serial number within nature

            2. Identificator Handler bears a Pandas DataFrame called NATURE with columns
                ["id" (int32), name" (string), "counter"(int64)]


            # a dictionary called nature_counter, regarding
            #     the model: { nature(object) : counter (int), }
            #
            # 3. Identificator Handler bears a list called NATURES, containing named tuples, which name is "Nature",
            #     and fields are "Id" and "Name"

            4. Generating an Identificator
                i.  Input: nature name (string) or nature id (int)
                ii. Method:
                    1) Get the nature object according to input, NATURES list
                    2) Get the counter for the nature in NATURES DataFrame
                    3) Increments its counter in dictionary and passes this counter to next step
                    4) Creates a return variable = nature code
                        a) Shifts left 58 bits
                        b) Bitwise OR with the counter
                    5) Returns the return variable

            5. Constructor
                5.1 Loads_Updates_Nature CSV





    """

    _DEFAULT_NATURES = {
        1: 'TraderAgent',
        2: 'GEEne',
        3: 'GuardianAngel',
        4: 'Overlord',
    }

    class NaturesCSVHandler:

        def __init__(self, filepath, container: 'IdHandler', delimiter=';'):
            self._filename = filepath
            self._csv_delimiter = delimiter
            self._container = container
            self._DEFAULT_NATURES = container.DEFAULT_NATURES
            self._NATURES_DF = None

        def loads_updates_csv(self) -> pd.DataFrame:
            """ Loads, Updates and sets Nature Attribute as pd.DataFrame

                If file can't be open, substitutes it with built-in
                DEFAULT NATURE DataFrame

                :returns: Nature DF attribute as reference

                MECHANISM

                1) Tries to load the NATURES csv file to DF
                    1) Success: Pass
                    2) Except (filenotfound, Permission): creates a new DF
                        with DEFAULT NATURES
                2) Checks whether Natures DF has multiple occurence of a given index
                    1) True: raise AttributeError
                    2) Else: Pass
                3) Parses DEFAULT NATURES
                    1) Current default nature not exists in DF?
                        1) True: Appends Default Nature to DF
                        2) False: Pass
                4) Set NATURES DF index as column 'Id'
                5) Returns DF
            """
            def _create_default_df():
                """ Creates DF with DEFAULT NATURES and attribs in CSV Handler"""
                ids = [key for key in self._DEFAULT_NATURES.keys()]
                names = [value for value in self._DEFAULT_NATURES.values()]
                self._NATURES_DF = pd.DataFrame({
                    'Id': ids,
                    'Name': names,
                    'Count': 0,
                })

            # (1) Tryes to read the csv file
            try:
                self._NATURES_DF = pd.read_csv(self._filename, delimiter=self._csv_delimiter)
            except (FileNotFoundError, PermissionError) as err:
                # If csv file does not exist, creates an empty DF with expected structure
                print("File missing or not allowed. Using default natures.")
                _create_default_df()
            except:
                print("Some unknown error occured when loading . Using default natures")
                _create_default_df()

            # (2) Checks whether Natures DF has multiple occurence of a given index
            # Create alias
            natures_df = self._NATURES_DF
            # Frequency distribution of Id's values
            id_freq_distr = natures_df['Id'].value_counts()
            # Amount of Id's which occur more than once
            multi_id_amount = len(id_freq_distr[id_freq_distr > 1])
            # Main test
            if multi_id_amount > 0:
                raise ValueError('A total of %d amount of nature Id have(has) multiple occurances. '
                                 'Should be zero.' % multi_id_amount)

            # (3) Parses DEFAULT NATURES
            # Create alias
            default_natures = self._DEFAULT_NATURES
            # Main parse
            for def_nature_id, def_nature_name in default_natures.items():
                # Current default nature not exists in DF?
                if def_nature_id not in natures_df['Id'].values:
                    # Appends current Default_Nature to DF
                    new_data = [def_nature_id, def_nature_name, 0]
                    new_columns = natures_df.columns
                    new_row = pd.DataFrame([new_data], columns=new_columns)
                    natures_df = natures_df.append(new_row)

            # (4) Set NATURES DF index as column 'Id'
            natures_df.set_index('Id')

    def __init__(self):
        self._filename = 'IdHandler_nature_counter.csv'
        self._csv_delimiter = ';'
        self._csv_handler = self.NaturesCSVHandler(self._filename,
                                                   self)

    def load_dataframe(self):
        # try:
        #     # Tryes to read the csv file
        #     self._NATURES = pd.read_csv(self._filename, delimiter=self._csv_delimiter)
        # except FileNotFoundError:
        #     # If csv file does not exist, creates an empty DF
        #     self._NATURES = pd.DataFrame({
        #         'id': pd.Series([], dtype='int'),
        #         'name': pd.Series([], dtype='str'),
        #         'count': pd.Series([], dtype='int'),
        #     })

        # # Checks whether all default natures exist id DF, including those which doesn't
        # # Creates an alias for the natures dataframe
        # naturesdf = self._NATURES
        # # Creates an alias for the default natures
        # natures = self._DEFAULT_NATURES
        # # Cicles through default natures
        """
        for nature in natures.keys():
            if nature in naturesdf:
                counts = naturesdf['id'].value_counts()[nature]
                if counts > 1:
                    raise ValueError('There must be a unique entry of a given nature id. Nature Id %s '
                                     'was found %d times.' % (nature, counts))
                elif natures[nature] != naturesdf
        """
        pass

    @property
    def DEFAULT_NATURES(self):
        return self._DEFAULT_NATURES

    @DEFAULT_NATURES.setter
    def DEFAULT_NATURES(self, *args, **kwargs):
        raise AttributeError("DEFAULT_NATURES is a read-only attribute.")

idhandler = IdHandler()
#idhandler._load_dataframe()


# Pandas tester

from random import randint
import pandas as pd

columns = ['Id', 'name', 'count']

test_data = [ [n, "Test %02d" % n, randint(1, 10)] for n in range(1, 11) ]

test_df = pd.DataFrame( test_data, columns=columns)

print(test_df)
