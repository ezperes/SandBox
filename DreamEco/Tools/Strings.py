""" DreamEco String tools"""

from difflib import SequenceMatcher
from typing import Iterable

from DreamEco.Bases.BaseClass import DreamBaseClass


def gauge_str_similarities(searched_strings: Iterable[str],
                           search_space: Iterable[str],
                           threshold: float = 0.8
                           ) -> dict:
    """Gauges the similarity ratio between strings within two lists.

    Args:
        searched_strings: Iterable[str] or str:
            A list which contains the strigs to be searched for.
        search_space: Iterable[str] or str:
            A list which contains the strings to be verified.
        threshold: 0 < float <= 1.0
            The minimun similarity ratio of strings so it is in returned dict.
    Returns:
        {searched_string: {search_space[i]: ratio}}, if ratio >= threshold.
    Raises:
        ValueError: When input's type mismatches expected ones.
    """

    def is_all_element_str(str_list: str) -> bool:
        """Checks whether all elements in an Iterable are strings."""
        return isinstance(str_list, Iterable)\
            and all(isinstance(truth, str) for truth in str_list)

    # def is_all_element_str(str_list: Iterable[str]) -> bool:
    #     """Checks whether all elements in an Iterable are strings."""

    def norm_str_list(input_str) -> [str]:
        """Returns a list of str, if input is str"""
        return [input_str] if isinstance(input_str, str)\
            else input_str

    def check_input_strlist(str_list, varname):
        if not is_all_element_str(str_list):
            raise ValueError(f'{varname} must be a string or'
                             ' an Iterable of strings.')

    def check_input_threshold(thresh):
        if (not isinstance(thresh, float) and thresh != 1) or\
                not 0.0 < thresh <= 1.0:
            raise ValueError(f'threshold must be a float'
                             ' within range (0.0, 1.0], or must be int = 1. ')

    verbosity = DreamBaseClass()
    verbosity.verbose(f"Running function: '{gauge_str_similarities.__name__}'.", 1)

    # 1. Normalizes input and creates aliases
    verbosity.verbose("Normalizing inputs.", 1)
    nsearched = norm_str_list(searched_strings)
    verbosity.verbose(f"nsearched = {nsearched}", 2)
    nspace = norm_str_list(search_space)
    verbosity.verbose(f"nspace = {nspace}", 2)

    # 2. Checks inputs
    verbosity.verbose("Checking inputs.", 1)
    check_input_strlist(nsearched, 'searched_strings')
    check_input_strlist(nspace, 'searched_strings')
    check_input_threshold(threshold)
    threshold = float(threshold)

    # 3. Creates output dictionary
    verbosity.verbose("Creating output dicionary.", 1)
    result = {searched_word: {tested_word:
                              SequenceMatcher(None,
                                              searched_word.upper(),
                                              tested_word.upper()).ratio()
                              for tested_word in nspace
                              if SequenceMatcher(None,
                                                 searched_word.upper(),
                                                 tested_word.upper()
                                                 ).ratio() >= threshold
                              }
              for searched_word in nsearched}
    verbosity.verbose("Filtering only searched words with at least a match.", 1)
    result = {key: value for key, value in result.items() if any(value)}

    # 4. Returns
    return result

