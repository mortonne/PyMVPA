# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##g
"""Parameter representation"""

__docformat__ = 'restructuredtext'

import re
import textwrap
import numpy as N
from mvpa.misc.state import IndexedCollectable

if __debug__:
    from mvpa.base import debug

_whitespace_re = re.compile('\n\s+|^\s+')

__all__ = [ 'Parameter', 'KernelParameter' ]

class Parameter(IndexedCollectable):
    """This class shall serve as a representation of a parameter.

    It might be useful if a little more information than the pure parameter
    value is required (or even only useful).

    Each parameter must have a value. However additional property can be
    passed to the constructor and will be stored in the object.

    BIG ASSUMPTION: stored values are not mutable, ie nobody should do

    cls.parameter1[:] = ...

    or we wouldn't know that it was changed

    Here is a list of possible property names:

        min   - minimum value
        max   - maximum value
        step  - increment/decrement stepsize
    """

    def __init__(self, default, name=None, doc=None, index=None, ro=False,
                 value=None, **kwargs):
        """Specify a Parameter with a default value and arbitrary
        number of additional parameters.

        Parameters
        ----------
        name : str
          Name of the parameter under which it should be available in its
          respective collection.
        doc : str
          Documentation about the purpose of this parameter.
        index : int or None
          Index of parameter among the others.  Determines order of listing
          in help.  If None, order of instantiation determines the index.
        ro : bool
          Either value which will be assigned in the constructor is read-only and
          cannot be changed
        value
          Actual value of the parameter to be assigned
        """
        self.__default = default
        self._ro = ro
        # XXX probably is too generic...
        # and potentially dangerous...
        # let's at least keep track of what is passed
        self._additional_props = []
        for k, v in kwargs.iteritems():
            self.__setattr__(k, v)
            self._additional_props.append(k)

        # needs to come after kwargs processing, since some debug statements
        # rely on working repr()
        IndexedCollectable.__init__(self, name=name, doc=doc, index=index,
                                      value=value)
        self._isset = False
        if self.value is None:
            self._set(self.__default, init=True)

        if __debug__:
            if kwargs.has_key('val'):
                raise ValueError, "'val' property name is illegal."



    def __str__(self):
        res = IndexedCollectable.__str__(self)
        # it is enabled but no value is assigned yet
        res += '=%s' % (self.value,)
        return res


    def __repr__(self):
        # cannot use IndexedCollectable's repr(), since the contructor
        # needs to handle the mandatory 'default' argument
        # TODO: so what? just tune it up ;)
        # TODO: think what to do with index parameter...
        s = "%s(%s, name=%s, doc=%s" % (self.__class__.__name__,
                                        self.__default,
                                        repr(self.name),
                                        repr(self.__doc__))
        plist = ["%s=%s" % (p, self.__getattribute__(p))
                    for p in self._additional_props]
        if len(plist):
            s += ', ' + ', '.join(plist)
        if self._ro:
            s += ', ro=True'
        if not self.isDefault:
            s += ', value=%r' % self.value
        s += ')'
        return s


    def doc(self, indent="  ", width=70):
        """Docstring for the parameter to be used in lists of parameters

        Returns
        -------
        string or list of strings (if indent is None)
        """
        paramsdoc = "  %s" % self.name
        if hasattr(paramsdoc, 'allowedtype'):
            paramsdoc += " : %s" % self.allowedtype
        paramsdoc = [paramsdoc]
        try:
            doc = self.__doc__
            if not doc.endswith('.'): doc += '.'
            try:
                doc += " (Default: %s)" % self.default
            except:
                pass
            # Explicitly deal with multiple spaces, for some reason
            # replace_whitespace is non-effective
            doc = _whitespace_re.sub(' ', doc)
            paramsdoc += ['  ' + x
                          for x in textwrap.wrap(doc, width=width-len(indent),
                                                 replace_whitespace=True)]
        except Exception, e:
            pass

        if indent is None:
            return paramsdoc
        else:
            return ('\n' + indent).join(paramsdoc)


    # XXX should be named reset2default? correspondingly in
    #     ParameterCollection as well
    def resetvalue(self):
        """Reset value to the default"""
        #IndexedCollectable.reset(self)
        if not self.isDefault and not self._ro:
            self._isset = True
            self.value = self.__default

    def _set(self, val, init=False):
        comparison = self._value != val
        isarray = isinstance(comparison, N.ndarray)
        if self._ro and not init:
            raise RuntimeError, \
                  "Attempt to set read-only parameter %s to %s" \
                  % (self.name, val)
        if (isarray and N.any(comparison)) or \
           ((not isarray) and comparison):
            if __debug__:
                debug("COL",
                      "Parameter: setting %s to %s " % (str(self), val))
            if hasattr(self, 'min') and val < self.min:
                raise ValueError, \
                      "Minimal value for parameter %s is %s. Got %s" % \
                      (self.name, self.min, val)
            if hasattr(self, 'max') and val > self.max:
                raise ValueError, \
                      "Maximal value for parameter %s is %s. Got %s" % \
                      (self.name, self.max, val)
            if hasattr(self, 'choices') and (not val in self.choices):
                raise ValueError, \
                      "Valid choices for parameter %s are %s. Got %s" % \
                      (self.name, self.choices, val)
            self._value = val
            # Set 'isset' only if not called from initialization routine
            self._isset = not init #True
        elif __debug__:
            debug("COL",
                  "Parameter: not setting %s since value is the same" \
                  % (str(self)))

    @property
    def isDefault(self):
        """Returns True if current value is bound to default one"""
        return self._value is self.default

    @property
    def equalDefault(self):
        """Returns True if current value is equal to default one"""
        return self._value == self.__default

    def setDefault(self, value):
        wasdefault = self.isDefault
        self.__default = value
        if wasdefault:
            self.resetvalue()
            self._isset = False

    # incorrect behavior
    #def reset(self):
    #    """Override reset so we don't clean the flag"""
    #    pass

    default = property(fget=lambda x:x.__default, fset=setDefault)
    value = property(fget=lambda x:x._value, fset=_set)

class KernelParameter(Parameter):
    """Just that it is different beast"""
    pass
