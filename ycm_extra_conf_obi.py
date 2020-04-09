#!/usr/bin/env python3

# This file is NOT licensed under the GPLv3, which is the license for the rest
# of YouCompleteMe.
#
# Here's the license text for this file:
#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org/>

from distutils.sysconfig import get_python_inc
import platform
import os
import io

import fnmatch
import logging
import subprocess
from pprint import pformat as PF
from pprint import pprint as PP
logging.basicConfig(level=logging.INFO)

throw_exceptions = True
use_additional_files=True


base_flags = [
    u'-x', u'c++'
]

base_flags_files=[
    os.path.expanduser('~') + os.path.sep + '.ycm_base_flags'
]

# These are the compilation flags that will be used in case there's no
# compilation database set (by default, one is not set).
# CHANGE THIS LIST OF FLAGS. YES, THIS IS THE DROID YOU HAVE BEEN LOOKING FOR.
fallback_flags = [
    u'-std=c++17',
    u'-Wall',
    u'-Wextra',
    u'-Werror',
    u'-Wno-long-long',
    u'-Wno-variadic-macros',
    u'-fexceptions',
    u'-ferror-limit=10000',
    u'-DNDEBUG',
]
fallback_flags_files=[
    '.clang_complete',
    '.ycm_fallback_flags',
    os.path.expanduser('~') + os.path.sep + '.ycm_fallback_flags'
]

source_ext = [ '.cpp', '.cxx', '.cc', '.c', '.m', '.mm' ]
header_ext = [ '.hpp', '.hxx', '.hh', '.h' ]

class FakeInfo(object):
    def __init__(self):
        self.compiler_flags_ = []
        self.include_dirs = []
        self.compiler_flags_end = []
        self.compiler_working_dir_ = None
    def __bool__(self):
        return self.compiler_flags_ != None
    def add_info(self,info):

        if not self.compiler_flags_:
            start=None
            end=None
            self.compiler_working_dir_ = info.compiler_working_dir_
            for item in info.compiler_flags_:
                if item.startswith("-I") and not start:
                    start=True
                elif start:
                    end=True

                if not start:
                    self.compiler_flags_.append(item)
                if not end:
                    self.include_dirs.append(item)
                else:
                    self.compiler_flags_end.append(item)
        else:
            for item in info.compiler_flags_:
                if item.startswith("-I") and item not in self.include_dirs:
                    self.include_dirs += item

    def close(self):
        self.compiler_flags_ += self.include_dirs
        self.compiler_flags_ += self.compiler_flags_end
# class FakeInfo

## finding stuff
def find_closest_path(path, target):
    candidate = os.path.join(path, target)
    if(os.path.isfile(candidate) or os.path.isdir(candidate)):
        logging.info("closest " + target + " at " + candidate)
        return candidate;
    else:
        parent = os.path.dirname(os.path.abspath(path));
        if(parent == path):
            #end recursion
            return None
        return find_closest_path(parent, target)

def find_closest_db(path, target):
    candidates = [ os.path.join(path, target)
                 , os.path.join(path+"-build","current", target)
                 , os.path.join(path+"-build", target)
                 , os.path.join(path,"build", target)
                 ]
    for candidate in candidates:
        print("checking: " + candidate)
        if(os.path.isfile(candidate) or os.path.isdir(candidate)):
            logging.info("closest " + target + " at " + candidate)
            return candidate, path;
    # not found in this iteration -> recurse
    parent = os.path.dirname(os.path.abspath(path));
    if(parent == path):
        #end recursion
        print("recuse end")
        return None, None
    print("recuse: " + parent)
    return find_closest_db(parent, target)

def flags_for_closest_include(filename):
        flags = []
        include_path = find_closest_path(filename, 'include')
        if include_path:
            logging.info("found include dir")
            flags.append("-I")
            flags.append(include_path)
        else:
            logging.info("no include dir found")
        return flags

def find_database(filename):
    # Do NOT import ycm_core at module scope.
    import ycm_core

    compilation_db_path , source_path = find_closest_db(filename, 'compile_commands.json')
    if not compilation_db_path:
        return None, None
    compilation_db_dir = os.path.dirname(compilation_db_path)
    logging.info("Set compilation database directory to " + compilation_db_dir)
    compilation_db =  ycm_core.CompilationDatabase(compilation_db_dir)

    if not compilation_db:
        logging.info("Compilation database file found but unable to load")
        return None, None
    return compilation_db, source_path

def flags_from_file(flags_file_candidate, source_file):
    flag_file = None
    logging.info("trying extra file: {}".format(flags_file_candidate))
    if os.path.isabs(flags_file_candidate) and os.path.exists(flags_file_candidate):
        flag_file = flags_file_candidate
    else:
        flag_file = find_closest_path(source_file, flags_file_candidate)

    if not flag_file:
        return []

    with io.open(flag_file, mode="r", encoding="utf-8") as fh:
        logging.info("adding flags from {}".format(flag_file))
        directory = os.path.dirname(flag_file)
        new_flags = []
        for line in fh:
            if not line.startswith("#"):
                logging.debug("adding flag {}".format(line.rstrip()))
                new_flags.append(line.rstrip())

    if source_file:
        return make_relative_flags_to_absolute(new_flags, directory)
    else:
        return new_flags

def flags_from_file_list(file_list, source_file):
        flags = []
        for candidate in file_list:
            new_falgs = flags_from_file(candidate, source_file)
            if new_falgs:
                flags += new_falgs
                logging.info("adding {} from file {}".format(str(new_falgs), candidate))
        return flags

## finding stuff - end
## simple helper
def is_header(filename):
    extension = os.path.splitext(filename)[1]
    return extension in header_ext

def make_relative_flags_to_absolute(flags, working_directory):
    if not working_directory:
        return list(flags)
    new_flags = []
    make_next_absolute = False
    path_flags = [ '-isystem', '-I', '-iquote', '--sysroot=' ]
    for flag in flags:
        new_flag = flag

        if make_next_absolute:
            make_next_absolute = False
            if not flag.startswith('/'):
                new_flag = os.path.join(working_directory, flag)

        for path_flag in path_flags:
            if flag == path_flag:
                make_next_absolute = True
                break

            if flag.startswith(path_flag):
                path = flag[ len(path_flag): ]
                new_flag = path_flag + os.path.join(working_directory, path)
                break

        if new_flag:
            new_flags.append(new_flag)
    return new_flags

def string_vector_to_list(string_vector):
    return [ str(x) for x in string_vector ]

def string_vector_to_str(string_vector):
    return str([ str(x) for x in string_vector ])


## simple helper - end
## using database / c interface
def get_flags_from_compilation_database(database, filename):
    #try:
    compilation_info, override_file = get_info_for_file_from_database(database, filename)
    #except Exception as e:
    #    logging.info("No compilation info for " + filename + " in compilation database")
    #    if throw_exceptions:
    #        raise e
    #    else:
    #        return None, None
    if not compilation_info:
        logging.info("No compilation info for " + filename + " in compilation database")
        return None, None

    #if not compilation_info.compiler_flags_:
    if not string_vector_to_list(compilation_info.compiler_flags_):
        logging.error("flags empty")
        logging.error("tried to use database in {}".format(database))
        logging.error(compilation_info.compiler_flags_)
        return None, None

    logging.info("found CompilationInfo for : " + filename)
    logging.debug("dir" + PF(dir(compilation_info)))
    #logging.debug("vars" + PF(vars(compilation_info)))
    #logging.debug("__dict__" + PF(compilation_info.__dict__))
    logging.debug("dir" + PF(compilation_info.compiler_flags_))
    logging.debug("flags: " + string_vector_to_str(compilation_info.compiler_flags_))
    logging.debug("workingdir:" + str(compilation_info.compiler_working_dir_))
    logging.debug("flags: " + string_vector_to_str(compilation_info.compiler_flags_))

    return make_relative_flags_to_absolute(
        compilation_info.compiler_flags_,
        compilation_info.compiler_working_dir_), override_file

def get_info_for_file_from_database(database, filename):
    logging.debug("database:" + PF(database))
    if not is_header(filename):
        logging.info("is cpp file")
        return database.GetCompilationInfoForFile(filename), None
    else:
        #find matching source file
        logging.info("is header file")
        basename = os.path.splitext(filename)[0]
        for extension in source_ext:
            replacement_file = basename + extension
            if os.path.exists(replacement_file):
                compilation_info = database.GetCompilationInfoForFile(replacement_file)
                if compilation_info.compiler_flags_:
                    return compilation_info, replacement_file

        #use any source file in the headers directory
        dpath = os.path.dirname(filename)
        for f in os.listdir(dpath):
            #skip non source files
            extension = os.path.splitext(f)[1]
            if extension not in source_ext:
                continue

            #get and join compilation for all cpp files in dir
            fpath = dpath + os.path.sep + f
            compilation_info = FakeInfo()
            tmp_info = database.GetCompilationInfoForFile(fpath)
            if tmp_info:
                compilation_info.add_info(tmp_info)
            compilation_info.close()
            if compilation_info.compiler_flags_:
                return compilation_info, None

        return None, None
## using database - end


# Called by vim Plugin
def Settings( **kwargs ):
  language = kwargs[ 'language' ]

  if language == 'cfamily':
    # If the file is a header, try to find the corresponding source file and
    # retrieve its flags from the compilation database if using one. This is
    # necessary since compilation databases don't have entries for header files.
    # In addition, use this source file as the translation unit. This makes it
    # possible to jump from a declaration in the header file to its definition
    # in the corresponding source file.
    filename = kwargs[ 'filename' ]
    logging.info("filename:" + filename)
    override_file = None
    final_flags = []

    database, source_dir = find_database(filename)
    logging.info("filename:" + filename)
    print("file: " + filename +"\n")
    if database:
        final_flags, override_file = get_flags_from_compilation_database(database, filename)
    else:
        #TODO fix me
        source_dir = 'something something'

    db_used = True
    if not final_flags:
        db_used = False
        final_flags = []

    if not db_used and use_additional_files:
        logging.warning("checking addional files")
        final_flags += flags_from_file_list(fallback_flags_files, filename)

    if not db_used:
        logging.warning("using fallback strategy to get flags")
        final_flags += fallback_flags
        final_flags += flags_for_closest_include(filename)

    final_flags = flags_from_file_list(base_flags_files, None) + final_flags #use this for tool-chaing etc
    final_flags = base_flags + final_flags

    rv = {
      'flags': final_flags,
      'include_paths_relative_to_dir': source_dir,
    }

    if override_file:
      rv['override_filename'] = override_file

    return rv

  if language == 'python':
    return {
      'interpreter_path': '/usr/bin/python3'
    }

  return {}

# For testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    import sys
    for filename in sys.argv[1:]:
        print("file: " + filename +"\n")
        input_dict = { "filename" : filename , "language" : "cfamily" }
        settings = Settings(**input_dict)
        print("final result:\n" + PF(settings))
