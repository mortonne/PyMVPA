#!/usr/bin/env python
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Python distutils setup for PyMVPA"""

from numpy.distutils.core import setup, Extension
import glob
import shutil
import os
import sys
import fnmatch
import lib2to3.main
from io import StringIO


EXTRA_2TO3_FLAGS = {'*': '-x import'}

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
TEMP = os.path.normpath(os.path.join(BASE, '_py3k'))


def custom_mangling(filename):
    pass

def walk_sync(dir1, dir2, _seen=None):
    if _seen is None:
        seen = {}
    else:
        seen = _seen

    if not dir1.endswith(os.path.sep):
        dir1 = dir1 + os.path.sep

    # Walk through stuff (which we haven't yet gone through) in dir1
    for root, dirs, files in os.walk(dir1):
        sub = root[len(dir1):]
        if sub in seen:
            dirs = [x for x in dirs if x not in seen[sub][0]]
            files = [x for x in files if x not in seen[sub][1]]
            seen[sub][0].extend(dirs)
            seen[sub][1].extend(files)
        else:
            seen[sub] = (dirs, files)
        if not dirs and not files:
            continue
        yield os.path.join(dir1, sub), os.path.join(dir2, sub), dirs, files

    if _seen is None:
        # Walk through stuff (which we haven't yet gone through) in dir2
        for root2, root1, dirs, files in walk_sync(dir2, dir1, _seen=seen):
            yield root1, root2, dirs, files


def sync_2to3(src, dst, clean=False):

    to_convert = []

    for src_dir, dst_dir, dirs, files in walk_sync(src, dst):
        for fn in dirs + files:
            src_fn = os.path.join(src_dir, fn)
            dst_fn = os.path.join(dst_dir, fn)

            # skip temporary etc. files
            if fn.startswith('.#') or fn.endswith('~'):
                continue

            # remove non-existing
            if os.path.exists(dst_fn) and not os.path.exists(src_fn):
                if clean:
                    if os.path.isdir(dst_fn):
                        shutil.rmtree(dst_fn)
                    else:
                        os.unlink(dst_fn)
                continue

            # make directories
            if os.path.isdir(src_fn):
                if not os.path.isdir(dst_fn):
                    os.makedirs(dst_fn)
                continue

            dst_dir = os.path.dirname(dst_fn)
            if os.path.isfile(dst_fn) and not os.path.isdir(dst_dir):
                os.makedirs(dst_dir)

            # don't replace up-to-date files
            try:
                if os.path.isfile(dst_fn) and \
                       os.stat(dst_fn).st_mtime >= os.stat(src_fn).st_mtime:
                    continue
            except OSError:
                pass

            # copy file
            if not os.path.islink(src_fn):
                shutil.copyfile(src_fn, dst_fn)
            elif not os.path.islink(dst_fn):
                # replicate ths symlink at the destination if doesn't exist yet
                os.symlink(os.readlink(src_fn), dst_fn)

            # add .py files to 2to3 list
            if dst_fn.endswith('.py'):
                to_convert.append((src_fn, dst_fn))

    # run 2to3
    flag_sets = {}
    for fn, dst_fn in to_convert:
        flag = ''
        for pat, opt in EXTRA_2TO3_FLAGS.items():
            if fnmatch.fnmatch(fn, pat):
                flag = opt
                break
        flag_sets.setdefault(flag, []).append(dst_fn)

    for flags, filenames in flag_sets.items():
        if flags == 'skip':
            continue

        _old_stdout = sys.stdout
        try:
            sys.stdout = StringIO()
            lib2to3.main.main("lib2to3.fixes", ['-w'] + flags.split()+filenames)
        finally:
            sys.stdout = _old_stdout

    for fn, dst_fn in to_convert:
        # perform custom mangling
        custom_mangling(dst_fn)


if sys.version_info[:2] < (2, 6):
    raise RuntimeError("PyMVPA requires Python 2.6 or higher")

# some config settings
bind_libsvm = 'local' # choices: 'local', 'system', None

libsvmc_extra_sources = []
libsvmc_include_dirs = []
libsvmc_libraries = []

extra_link_args = []
libsvmc_library_dirs = []

requires = {
    'core': [
        'scipy',
        'nibabel'
    ]
}

# platform-specific settings
if sys.platform == "darwin":
    extra_link_args.append("-bundle")

if sys.platform.startswith('linux'):
    # need to look for numpy (header location changes with v1.3)
    from numpy.distutils.misc_util import get_numpy_include_dirs
    libsvmc_include_dirs += get_numpy_include_dirs()

# when libsvm is forced -- before it was used only in cases
# when libsvm was available at system level, hence we switch
# from local to system at this point
# TODO: Deprecate --with-libsvm for 0.5
for arg in ('--with-libsvm', '--with-system-libsvm'):
    if not sys.argv.count(arg):
        continue
    # clean argv if necessary (or distutils will complain)
    sys.argv.remove(arg)
    # assure since default is 'auto' wouldn't fail if it is N/A
    bind_libsvm = 'system'

# when no libsvm bindings are requested explicitly
if sys.argv.count('--no-libsvm'):
    # clean argv if necessary (or distutils will complain)
    sys.argv.remove('--no-libsvm')
    bind_libsvm = None

# if requested:
if bind_libsvm == 'local':
    # we will provide libsvm sources later on # if libsvm.a is available locally -- use it
    #if os.path.exists(os.path.join('build', 'libsvm', 'libsvm.a')):
    libsvm_3rd_path = os.path.join('3rd', 'libsvm')
    libsvmc_include_dirs += [libsvm_3rd_path]
    libsvmc_extra_sources = [os.path.join(libsvm_3rd_path, 'svm.cpp')]
elif bind_libsvm == 'system':
    # look for libsvm in some places, when local one is not used
    libsvmc_libraries += ['svm']
    if not sys.platform.startswith('win'):
        libsvmc_include_dirs += [
            '/usr/include/libsvm-3.0/libsvm',
            '/usr/include/libsvm-2.0/libsvm',
            '/usr/include/libsvm',
            '/usr/local/include/libsvm',
            '/usr/local/include/libsvm-2.0/libsvm',
            '/usr/local/include']
    else:
        # no clue on windows
        pass
elif bind_libsvm is None:
    pass
else:
    raise ValueError("Shouldn't happen that we get bind_libsvm=%r"
                     % (bind_libsvm,))


# define the extension modules
libsvmc_ext = Extension(
    'mvpa2.clfs.libsvmc._svmc',
    sources=libsvmc_extra_sources + [os.path.join('mvpa2', 'clfs', 'libsvmc', 'svmc.i')],
    include_dirs=libsvmc_include_dirs,
    library_dirs=libsvmc_library_dirs,
    libraries=libsvmc_libraries,
    language='c++',
    extra_link_args=extra_link_args,
    swig_opts=['-I' + d for d in libsvmc_include_dirs])

smlrc_ext = Extension(
    'mvpa2.clfs.libsmlrc.smlrc',
    sources=[ os.path.join('mvpa2', 'clfs', 'libsmlrc', 'smlr.c') ],
    #library_dirs = library_dirs,
    libraries=['m'] if not sys.platform.startswith('win') else [],
    # extra_compile_args = ['-O0'],
    extra_link_args=extra_link_args,
    language='c')

ext_modules = [smlrc_ext]

if bind_libsvm:
    ext_modules.append(libsvmc_ext)

# Notes on the setup
# Version scheme is: major.minor.patch<suffix>

def get_full_dir(path):
    path_split = path.split(os.path.sep) # so we could run setup.py on any platform
    path_proper = os.path.join(*path_split)
    return (path_proper,
            [f for f in glob.glob(os.path.join(path_proper, '*'))
             if os.path.isfile(f)])

# borrowed from https://wiki.python.org/moin/Distutils/Tutorial
## Code borrowed from wxPython's setup and config files
## Thanks to Robin Dunn for the suggestion.
## I am not 100% sure what's going on, but it works!
def opj(*args):
    path = os.path.join(*args)
    return os.path.normpath(path)

def find_data_files(srcdir, *wildcards, **kw):
    # get a list of all files under the srcdir matching wildcards,
    # returned in a format to be used for install_data
    file_list = []
    recursive = kw.get('recursive', True)
    for d, dirs, files in os.walk(srcdir, topdown=True):
        for wc in wildcards:
            files_ = [opj(d, x) for x in fnmatch.filter(files, wc)]
            if files_:
                file_list.append((d, files_))
        if not recursive:
            break # one would be enough ;)

    return file_list

# define the setup
def setup_package():
    # Perform 2to3 if needed
    local_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    src_path = local_path
    if sys.version_info[0] == 3:
        src_path = os.path.join(local_path, 'build', 'py3k')
        print("Converting to Python3 via 2to3...")
        sync_2to3('mvpa2', os.path.join(src_path, 'mvpa2'))
        sync_2to3('3rd', os.path.join(src_path, '3rd'))

        # Borrowed from NumPy before this code was deprecated (everyone
        # else moved on from 2to3)
        # Ugly hack to make pip work with Python 3, see NumPy #1857.
        # Explanation: pip messes with __file__ which interacts badly with the
        # change in directory due to the 2to3 conversion.  Therefore we restore
        # __file__ to what it would have been otherwise.
        global __file__
        __file__ = os.path.join(os.curdir, os.path.basename(__file__))
        if '--egg-base' in sys.argv:
            # Change pip-egg-info entry to absolute path, so pip can find it
            # after changing directory.
            idx = sys.argv.index('--egg-base')
            if sys.argv[idx + 1] == 'pip-egg-info':
                sys.argv[idx + 1] = os.path.join(local_path, 'pip-egg-info')

    # Run build
    os.chdir(src_path)
    sys.path.insert(0, src_path)

    setup(name='pymvpa2',
          version='2.6.5.dev1',
          author='Michael Hanke, Yaroslav Halchenko, Nikolaas N. Oosterhof',
          author_email='pkg-exppsy-pymvpa@lists.alioth.debian.org',
          license='MIT License',
          url='http://www.pymvpa.org',
          description='Multivariate pattern analysis',
          long_description=
              "PyMVPA is a Python module intended to ease pattern classification "
              "analyses of large datasets. It provides high-level abstraction of "
              "typical processing steps and a number of implementations of some "
              "popular algorithms. While it is not limited to neuroimaging data "
              "it is eminently suited for such datasets.\n"
              "PyMVPA is truly free software (in every respect) and "
              "additionally requires nothing but free-software to run.",
          install_requires=['numpy', 'bleach', 'pygments', 'scipy', 'nibabel', 'joblib'],
          # please maintain alphanumeric order
          packages=[ 'mvpa2',
                     'mvpa2.algorithms',
                     'mvpa2.algorithms.benchmarks',
                     'mvpa2.atlases',
                     'mvpa2.base',
                     'mvpa2.clfs',
                     'mvpa2.clfs.libsmlrc',
                     'mvpa2.clfs.libsvmc',
                     'mvpa2.clfs.skl',
                     'mvpa2.clfs.sg',
                     'mvpa2.cmdline',
                     'mvpa2.datasets',
                     'mvpa2.datasets.sources',
                     'mvpa2.featsel',
                     'mvpa2.kernels',
                     'mvpa2.mappers',
                     'mvpa2.mappers.glm',
                     'mvpa2.generators',
                     'mvpa2.measures',
                     'mvpa2.misc',
                     'mvpa2.misc.bv',
                     'mvpa2.misc.fsl',
                     'mvpa2.misc.io',
                     'mvpa2.misc.plot',
                     'mvpa2.misc.surfing',
                     'mvpa2.sandbox',
                     'mvpa2.support',
                     'mvpa2.support.afni',
                     'mvpa2.support.bayes',
                     'mvpa2.support.nipy',
                     'mvpa2.support.ipython',
                     'mvpa2.support.nibabel',
                     'mvpa2.support.scipy',
                     'mvpa2.testing',
                     'mvpa2.tests',
                     'mvpa2.tests.badexternals',
                     'mvpa2.viz',
                   ],
          data_files=[('mvpa2', [os.path.join('mvpa2', 'COMMIT_HASH')])]
                     + find_data_files(os.path.join('mvpa2', 'data'),
                                       '*.txt', '*.nii.gz', '*.rtc', 'README', '*.bin',
                                       '*.dat', '*.dat.gz', '*.mat', '*.fsf', '*.par'),
          scripts=glob.glob(os.path.join('bin', '*')),
          ext_modules=ext_modules
          )


if __name__ == '__main__':
    setup_package()
