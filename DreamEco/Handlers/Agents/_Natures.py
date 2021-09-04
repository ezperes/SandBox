"""Dream Company Ecosystem: Agents: Nature Handler Module

        PURPOSE
            To centralize, discipline and manage the states (attributes) and
            behavior (methods) of
                1. Existance
                2. Storage
                3. Retrieval
                3. Rules Compliance
                4. Provisioning of information to whoever be interested
            of the NATURE of the myriad of AGENTS to be SPAWNED
            within DreamEco

        AGENTS NATURE DEFINITION
            The DREAM COMPANY ECOSYSTEM - DreamEco, and its subecosystems (e.g.:
            Trade Ecosystem - TradEco) are implemented as set of computational objects
            which, once instatiated, are seen as AGENTS, and each of them complies its
            specific role within Ecosystem, according to its NATURE.

        AGENTS NATURE EXAMPLES
            The current examples of Agent's Nature are:
                1. Overlord
                2. Guardian Angel
                3. GEEEne
                4. Trader Agent

        NATURES HANDLER SPAWING RULES
            1) There shall be only *ONE* spawned per Dream Company Ecosystem - DreamEco

        NATURES RULES
#done
            1. Natures are defined by the attributes:
                1. Id: a 6 bits non-nagtive integer.
                2. Name: a brief string name (max 64 char)
                3. Definition: a brief multi-line string description
#done
            2. These attributes are unique:
                1. Id
                2. Name
#done
            3. There is a default initial set of natures, in module's root namespace,
                1. Such initial data is defined by a class with the attributes:
                    1. Fields: a list with the names of the fields (columns), in str.
                    2. Data: a list of lists, being each inner list the data of each default
                        nature, each element corresponding to the data of a column,
                        regarding columns order.
                    3. The name of class is _DEFAULT_NATURES
                2. These data are included to the file, if the given ID does not exist in it
                    1. In case of ID collision, the file entry prevails

            4. Existant natures are those listed in the "natures.csv", which accomplish
                the non-volatile storage of nature definition data

            5. The storage in runtime volatile memory is in terms of a pd.DataFrame,
                with the aforementionend structure

            6. The csv file is automatically saved when this Handler is about to
                be destroyed

            7. The inclusion of a new nature is done by *include* public method, which verifies the
                rules compliance by the new entry

            8. The obtaining of the current Natures is in terms of a pd.DataFrame,
                with the aforementionend structure, by the *return* of the *get_natures*
                public method


"""

# Module current version
__version__ = '0.0.1'

from typing import Iterable

import pandas as pd

from DreamEco.Bases import DreamBaseClass
from DreamEco.Tools.Strings import gauge_str_similarities

# Default parameters
d_filepath = 'natures.csv'
d_delimiter = ';'


# Defualt Natures
class _DEFUALT_NATURES:
    """ Minimun DataSet for DEFAULT NATURES non-volatile storage """
    fields = [
        'Id',
        'Name',
        'Definition',
    ]
    columns = fields
    _index_column = 0
    index_column = columns[_index_column]
    data = [
        [1,
         'Overlord',
         """
    Overlord is the main Agent of the TradeEcosystem.
    
    It is responsible to get data from outer world, turns it into information, 
    and bring such information into intelligence.
    Coordinates, from the long-term and short-term strategic scope, the actions 
    of subordinated agents, so each agent tends to accomplish not only their individuals 
    objectives, but also the collective overall objetcive.""",
         ],
        [2,
         'Guardian Angel',
         """
    Guardian Angel is responsible to make to happen a specific set of risk/goal policy.
    
    Given a set of integrated risk/goal rules, such set is taken by the Guardian Angel, who 
    is in charge to spawn the required subordinated agents and hadles their individual goals 
    in terms of risk and objectives.""",
         ],
        [3,
         'GEEEne',
         """
    Genetic Evolutionary Environment Engine - GEEEne
    
    The virtual environment in which the intermediate metaheurisc process (evolutionary) happens.
    GEEEne - Genetic Evolutionary Environment Engine - is the component of TradeEco responsible to perform 
    the intermediate metaheuristics activity within TradeEco's automatic trading metaheuristis chain, 
    by deploying a virtual environment which provides means for the emerging of the 
    most suitable trade setups within a given market state.""",
         ],
        [4,
         'Trader Agent',
         """
    Trader Agent is the elementary component of TradeEco.
    
    It is the genetic individual acting according to its genetic contruction information (genotype), and its own
    adaptations according to environment circumstances (phenotype). Its activity log feeds the database to which the
    Overlord shall reccur to so it can construct its genetic data bank. 
         """,
         ],
    ]


class NaturesHandler(DreamBaseClass):
    """Dream Company Ecosystem: Agents: Nature Handler

    Handles Natures within DreamEco, according to Nature's
    definitions and rules wihtin Agents_Natures module documentation.
    """
    # Class Metainformation
    class Meta(DreamBaseClass.Meta):
        # Class version
        __version__ = '0.0.1'
        # Maximum allowed number of concurrent spawned agents
        __max_spawn__ = 1

    def __init__(self, filepath=d_filepath,
                 container: 'object' = None,
                 delimiter: str = d_delimiter,
                 verbosity_level=None):
        """Inits NaturesHandler object.

        Args:
            filepath: Optional; The csv file path and name containing natures.
                String or path object. Default is in d_filepath module var.
            container: Optional; Any object which contains the current initing NaturesHandler
                object. Needed so the contruction hierarchy can be traced. Any object.
            delimiter: Optional; The default delimiter is in d_delimiter module var. Str.
        """
        self._filepath = filepath
        self._csv_delimiter = delimiter
        self._container = container
        self._default_natures = _DEFUALT_NATURES.data
        self._index = _DEFUALT_NATURES.index_column  # Dataframe index column
        self._columns = _DEFUALT_NATURES.columns  # DataFrame columns list
        # DataFrame which bears current loaded Natures
        self._empty_natures_df()
        # Class Verbosity Init
        DreamBaseClass.__init__(self, verbosity_level=verbosity_level)

    def _empty_natures_df(self):
        """Resets _natures_df """
        self._natures_df = pd.DataFrame(columns=self._columns)
        self._natures_df = self._natures_df.set_index(self._index)

    # Tested by Zucarato in 2021/08/28
    def check_rules(self, nature_id: int, nature_name: str, nature_definition: str) -> bool:
        """Checks whether input data complies Natures' rules

        Tests each input data if it fits Natures rules, so they can be cast into Natures
        DataFrame as a new Nature entry.

        Args:
            nature_id: int: a 6 bits non-nagtive integer.
            nature_name: a brief string name (max 64 char).
            nature_definition: a brief multi-line string description.
        Returns:
            Bool: True if all rules are satisfyed. False otherwise.
        """

        self.verbose("Checking Nature's rules", 1)

        # 1. Checks Id (6-bits positive integer)
        if not isinstance(nature_id, int):
            self.verbose('nature_id must be a integer', 0)
            return False
        if not 0 <= nature_id <= 0b111111:
            self.verbose('nature_id must be a 6-bit positive integer', 0)
            return False
        # 1.1 Checks Id uniqueness
        self.verbose("Nature's DF columns: " + self._natures_df.columns,2)
        self.verbose("Nature's DF", 2)
        self.verbose(self._natures_df, 2)
        if nature_id in self._natures_df.index:
            self.verbose(f'{nature_id} already existis in Natures records. Must be unique.', 0)
            return False

        # 2. Checks Name
        self.verbose('Checking Nature "Name" rules compliance.', 1)
        if not isinstance(nature_name, str):
            self._verbosity.verbose('nature_name must be a string with'
                                    'at most 64 char lenght', 0)
            return False
        if not len(nature_name) <= 64:
            self.verbose('nature_name must be a string with'
                                    'at most 64 char lenght', 0)
            return False
        # 2.1 Cheks name uniqueness
        # Creates a dict with similarities >= 80%
        similarities = gauge_str_similarities(nature_name, self._natures_df['Name'], .5)
        # If any similarity, checks if any of them = 1
        if any(similarities):
            self.verbose("Creates a list with similarities ratios.", 1)
            sim_ratios = []
            [sim_ratios.extend(value.values()) for value in similarities.values()]
            self.verbose("Checking if any ratio is 1 (perfect match)", 1)
            if any(value == 1.0 for value in sim_ratios):
                self.verbose("Returns False", 1)
                self.verbose(f"Name {nature_name} is not unique."
                             f"These is (are) similarity(ies) found:", 0)
                self.verbose(similarities, 0)
                return False
            else:
                self.verbose("Warns for great similarity, and goes on.", 1)
                self.verbose(f"Name {nature_name} has similarity (ies) found."
                             f"These is (are) similarity(ies) found:", 0)
                self.verbose(similarities, 0)

        # 3. Checks natures 'definition' rules
        self.verbose("Checking Natures 'Definition' rules.", 1)
        if not isinstance(nature_definition, str):
            self.verbose("'nature_definition' must be a string.", 0)
            return False

        # 4. All rules are complied.
        self.verbose("All rules are met. Returns True.", 1)
        return True

    def include(self, nature_id: int = None,
                nature_name: str = None,
                nature_definition: str = None):
        """Includes a new nature definition into _natures_df.
        Checks rules first.

        Args:
            nature_id: Optional: int: a 6 bits non-nagtive integer.
                If ommited, includes as the last Id + 1
            nature_name: a brief string name (max 64 char).
            nature_definition: a brief multi-line string description.
        Raises:
            ValueError: If some rule is not satisfied.
        """

        # If nature_id is None, sets to it the greatest Id + 1
        if nature_id is None:
            max_id = int(self._natures_df.index.max())
            nature_id = max_id + 1

        # If all parameters are ok
        if self.check_rules(nature_id, nature_name, nature_definition):
            # Creates new row in DF
            self._natures_df.loc[nature_id] = {
                self._columns[1]: nature_name,
                self._columns[2]: nature_definition
            }
        # Parameters not ok
        else:
            raise ValueError("Natures parameters not accepted. Nature not created.")

    def _loads_updates_natures_df(self):
        """ Loads, Updates and sets _natures_df attribute as a pd.DataFrame.

            If file can't be open, fills _natures_df it with built-in
            _DEFAULT_NATURES global var data.

            INPUT DATA:
                1) Module Globals:
                    _DEFAULT_NATURES: class:
                        The default data do fill _natures_df, if file can't
                        be open.
                2) Class Attributes:
                    _filepath: Str or path obj:
                        Path to .csv source.
                    _csv_delimiter: str:
                        Delimiter of fields in .csv.

            OUTPUT:
                1) Class Attribs:
                    _natures_df: pd.DataFrame:
                        Dataframe which stores the current valid natures.

            MECHANISM:
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
            self._empty_natures_df()
            for nature in self._default_natures:
                self.include(*nature)

        # (1) Tryes to read the csv file
        try:
            self._natures_df = pd.read_csv(self._filepath, delimiter=self._csv_delimiter)
            # loaded_natures = pd.read_csv(self._filepath, sep=self._csv_delimiter)

            self._natures_df = self._natures_df.set_index(self._index)
        except (FileNotFoundError, PermissionError) as err:
            # If csv file does not exist, creates an empty DF with expected structure
            print("File missing or not allowed. Using default natures.")
            _create_default_df()
        except:
            print("Some unknown error occured when loading . Using default natures")
            _create_default_df()

        # (2) Checks whether Natures DF has multiple occurence of a given index
        # Create alias
        natures_df = self._natures_df
        # Frequency distribution of Id's values
        id_freq_distr = natures_df.index.value_counts()
        # Amount of Id's which occur more than once
        multi_id_occurance = id_freq_distr[id_freq_distr > 1]
        multi_id_amount = len(multi_id_occurance)
        # Main test
        if any(multi_id_occurance):
            raise ValueError('A total amount of %d nature Id have(has) multiple occurances. '
                             'Should be zero.' % multi_id_amount)

        # (3) Parses DEFAULT NATURES
        for def_nature in self._default_natures:
            # Current default nature not exists in DF?
            if def_nature[0] not in natures_df.index:
                # Includes current Default_Nature to DF
                self.include(*def_nature)

    def _saves_natures_df(self):
        self.verbose(f"Saving _nature_df to {self._filepath} file.", 1)
        self._natures_df.to_csv(self._filepath, sep=self._csv_delimiter)


class tester_NaturesHandler(NaturesHandler):

    includeds = [
        [24, 'Adam', 'He-Man'],
        [51, 'Caninha 51', 'Pirassununga'],
    ]

    columns = _DEFUALT_NATURES.columns

    def __init__(self):
        super(tester_NaturesHandler, self).__init__(verbosity_level=2)
        self._filepath = '/natures.csv'
        # self.test()
        self.test2()

    def test(self):
        for entry in self.includeds:
            self.include(*entry)

    def test2(self):
        self._loads_updates_natures_df()
        self.include(None, 'Youngster', 'Catarrento.')


tester = tester_NaturesHandler()
