from .. import simpleline as tui
from pyanaconda.ui.tui.tuiobject import TUIObject
from pyanaconda.ui.tui.spokes import collect_spokes
from pyanaconda.ui import common

class TUIHub(TUIObject, common.Hub):
    """Base Hub class implementing the pyanaconda.ui.common.Hub interface.
    It uses text based categories to look for relevant Spokes and manages
    all the spokes it finds to have the proper category.

    :param categories: list all the spoke categories to be displayed in this Hub
    :type categories: list of strings

    :param title: title for this Hub
    :type title: unicode

    """

    categories = []
    title = "Default HUB title"

    def __init__(self, app, data, storage, payload, instclass):
        TUIObject.__init__(self, app, data)
        common.Hub.__init__(self, data, storage, payload, instclass)

        self._spokes = {}     # holds spokes referenced by their class name
        self._keys = {}       # holds spokes referenced by their user input key
        self._spoke_count = 0

        # look for spokes having category present in self.categories
        for c in self.categories:
            spokes = collect_spokes(c)

            # sort them according to their priority
            for s in sorted(spokes, key = lambda s: s.priority):
                spoke = s(app, data, storage, payload, instclass)
                spoke.initialize()

                if not spoke.showable:
                    spoke.teardown()
                    del spoke
                    continue

                self._spoke_count += 1
                self._keys[self._spoke_count] = spoke
                self._spokes[spoke.__class__.__name__] = spoke


    def refresh(self, args = None):
        """This methods fills the self._window list by all the objects
        we want shown on this screen. Title and Spokes mostly."""
        TUIObject.refresh(self, args)

        def _prep(i, w):
            number = tui.TextWidget("%2d)" % i)
            return tui.ColumnWidget([(3, [number]), (None, [w])], 1)

        # split spokes to two columns
        left = [_prep(i, w) for i,w in self._keys.iteritems() if i % 2 == 1]
        right = [_prep(i, w) for i,w in self._keys.iteritems() if i % 2 == 0]

        c = tui.ColumnWidget([(39, left), (39, right)], 2)
        self._window.append(c)

        return True

    def input(self, key):
        """Handle user input. Numbers are used to show a spoke, the rest is passed
        to the higher level for processing."""
        try:
            number = int(key)
            self.app.switch_screen_with_return(self._keys[number])
            return None

        except (ValueError, KeyError):
            return key