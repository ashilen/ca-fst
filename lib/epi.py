from epitran import Epitran as Epi
from epitran.simple import (
    SimpleEpitran as SimpleEpi,
    defaultdict,
    os,
    pkg_resources,
    DatafileError,
    csv,
    unicodedata,
    re,
    MappingError
)


class ConfigurableEpitran(Epi):
    def __init__(self, code, *args, g2p_loc=None, **kwargs):
        super().__init__(code, *args, **kwargs)
        self.epi = ConfigurableSimpleEpitran(code, g2p_loc=g2p_loc)


class ConfigurableSimpleEpitran(SimpleEpi):

    def __init__(self, code, *args, g2p_loc=None, **kwargs):
        super().__init__(code, *args, **kwargs)
        self.g2p = self.__load_g2p_map(code, False, alt_loc=g2p_loc)

    def __load_g2p_map(self, code, rev, alt_loc=None):
        """Load the code table for the specified language.
        Args:
            code (str): ISO 639-3 code plus "-" plus ISO 15924 code for the
                        language/script to be loaded
            rev (boolean): True for reversing the table (for reverse transliterating)
        """
        g2p = defaultdict(list)
        gr_by_line = defaultdict(list)
        code += '_rev' if rev else ''
        try:
            path = alt_loc or os.path.join('data', 'map', code + '.csv')
            path = pkg_resources.resource_filename(__name__, path)
        except IndexError:
            raise DatafileError('Add an appropriately-named mapping to the data/maps directory.')
        with open(path, 'rb') as f:
            reader = csv.reader(f, encoding='utf-8')
            orth, phon = next(reader)
            if orth != 'Orth' or phon != 'Phon':
                raise DatafileError('Header is ["{}", "{}"] instead of ["Orth", "Phon"].'.format(orth, phon))
            for (i, fields) in enumerate(reader):
                try:
                    graph, phon = fields
                except ValueError:
                    raise DatafileError('Map file is not well formed at line {}.'.format(i + 2))
                graph = unicodedata.normalize('NFD', graph)
                phon = unicodedata.normalize('NFD', phon)
                if not self.tones:
                    phon = re.sub('[˩˨˧˦˥]', '', phon)
                g2p[graph].append(phon)
                gr_by_line[graph].append(i)
        if self._one_to_many_gr_by_line_map(g2p):
            graph, lines = self._one_to_many_gr_by_line_map(gr_by_line)
            lines = [l + 2 for l in lines]
            raise MappingError('One-to-many G2P mapping for "{}" on lines {}'.format(graph, ', '.join(map(str, lines))).encode('utf-8'))
        return g2p