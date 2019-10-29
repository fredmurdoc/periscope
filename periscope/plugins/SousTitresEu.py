# -*- coding: utf-8 -*-

#   This file is part of periscope.
#   Copyright (c) 2008-2011 Matias Bordese
#
#   periscope is free software; you can redistribute it and/or modify
#   it under the terms of the GNU Lesser General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   periscope is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public License
#   along with periscope; if not, write to the Free Software
#   Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging
import os
import re
import subprocess
import urllib
import urllib2

from bs4 import BeautifulSoup

import SubtitleDatabase


LANGUAGES = {"es": "Spanish"}


class SousTitresEu(SubtitleDatabase.SubtitleDB):
    url = "https://www.sous-titres.eu"
    site_name = "www.sous-titres.eu"
    guessedData = None
    def __init__(self, config, cache_folder_path):
        super(SousTitresEu, self).__init__(LANGUAGES,config=config,cache_folder_path=cache_folder_path)
        self.api_base_url = 'https://www.sous-titres.eu/search.html'

    def process(self, filepath, langs):
        '''Main method to call on the plugin.

        Pass the filename and the wished languages and it will query
        the subtitles source. Only Spanish available.
        '''

        fname = unicode(self.getFileName(filepath).lower())
        self.guessedData = self.guessFileData(fname)
        if self.guessedData['type'] == 'tvshow':
            subs = self.query(self.guessedData['name'],
                              self.guessedData['season'],
                              self.guessedData['episode'],
                              self.guessedData['teams'])
            return subs
        elif guessedData['type'] == 'movie':
            subs = self.query(guessedData['name'], extra=guessedData['teams'])
            return subs
        else:
            return []

    def _get_result_title(self, result):
        '''Return the title of the result.'''
        rs = result.find('span', {'class': 'smallFilenameSerie'})
        if rs:
            return rs.text
        else:
            rs = result.find('span', {'class': 'smallFilenameFilm'})
            if rs:
                return rs.text
            else:
                return None

    def _get_result_link(self, result):
        '''Return the absolute link of the result. (not the downloadble file)'''
        return '%s/%s' % (self.url, result.get('href'))

    def _get_download_link(self, result_url):
        '''Return the direct link of the subtitle'''
        return result_url
        
    def _get_result_lang(self, result):
        return result.find('img').get('alt')
    
    def query(self, name, season=None, episode=None, extra=None):
        '''Query on SubDivX and return found subtitles details.'''
        sublinks = []

        if season and episode:
            query = "%s s%02de%02d" % (name, season, episode)
        else:
            query = name

        params = {'q': query }
        encoded_params = urllib.urlencode(params)
        query_url = '%s?%s' % (self.api_base_url, encoded_params)

        logging.debug("SousTitresEu query: %s", query_url)

        content = self.downloadContent(query_url, timeout=5)
        if content is not None:
            logging.debug('analyse content')
            soup = BeautifulSoup(content, features="lxml")
            containers = soup.find_all("h3")
            target_parts = []
            if containers:
                logging.debug('fetch containers')
                logging.debug(containers)
                for container in containers:
                    logging.debug("name %s " % container.text)
                    if name.lower() in container.text.lower():
                        logging.debug("found  %s !!! " % container.text)
                        target_parts.append(container.parent)
            else:
                logging.warn('no containers to fecth')
                return None
            for target_part in target_parts:
                logging.debug('fetch in element : %s' % target_part)
                for subs in target_part.find_all('a', {'class': 'subList'}):
                    logging.debug('found element : %s' % subs)
                    title =self._get_result_title(subs)
                    logging.debug("title %s" % title.replace('.', ' '))
                    matched = False
                    if season and episode:
                        logging.debug("search %s with season %s episode %s in %s" % (name, season, episode, title)) 
                        matched = (str(season) in title) and (str(episode) in title) and (name.lower() in title.replace('.', ' ').lower())
                    else:
                        matched = name.lower() in title.replace('.', ' ').lower()
                    if matched:
                        logging.debug('match with title  : %s' % title)
                        result = {}
                        result["release"] = self._get_result_title(subs)
                        result["lang"] = self._get_result_lang(subs)
                        result["link"] = self._get_result_link(subs)
                        result["page"] = query_url
                        result["rating"] = None
                        sublinks.append(result)
        sorted_links = sorted(sublinks, key=lambda k: k['rating'], reverse=True)
        return sorted_links

    def createFile(self, subtitle):
        '''Download and extract subtitle.

        Pass the URL of the sub and the file it matches, will unzip it
        and return the path to the created file.
        '''
        download_url = self._get_download_link(subtitle["link"])
        subtitle["link"] = download_url
        request = urllib2.Request(download_url)
        request.get_method = lambda: 'HEAD'
        response = urllib2.urlopen(request)

        if response.url.endswith('.zip'):
            # process as usual
            return super(SousTitresEu, self).createFile(subtitle)
        elif response.url.endswith('.rar'):
            # Rar support based on unrar commandline, download it here:
            # http://www.rarlab.com/rar_add.htm
            # Install and make sure it is on your path
            logging.warning(
                'Rar is not really supported yet. Trying to call unrar')

            video_filename = os.path.basename(subtitle["filename"])
            base_filename, _ = os.path.splitext(video_filename)
            base_rar_filename, _ = os.path.splitext(subtitle["filename"])
            rar_filename = '%s%s' % (base_rar_filename, '.rar')
            self.downloadFile(download_url, rar_filename)

            try:
                args = ['unrar', 'lb', rar_filename]
                output = subprocess.Popen(
                    args, stdout=subprocess.PIPE).communicate()[0]

                for fname in output.splitlines():
                    base_name, extension = os.path.splitext(fname)
                    if extension in (".srt", ".sub", ".txt"):
                        wd = os.path.dirname(rar_filename)
                        final_name = '%s%s' % (base_filename, extension)
                        final_path = os.path.join(wd, final_name)
                        args = ['unrar', 'e', rar_filename, fname, wd]
                        output = subprocess.Popen(
                            args, stdout=subprocess.PIPE).communicate()[0]
                        tmp = os.path.join(wd, fname)
                        if os.path.exists(tmp):
                            # rename extracted subtitle file
                            os.rename(tmp, final_path)
                            return final_path
            except OSError:
                logging.exception("Execution failed: unrar not available?")
                return None
            finally:
                os.remove(rar_filename)
        else:
            logging.info(
                "Unexpected file type (not zip) for %s" % rar_filename)
            return None
