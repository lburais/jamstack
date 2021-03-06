# ###################################################################################################################################################
# Filename:     onenote.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:
# - Date:
#
# Graph Explorer:
#   https://developer.microsoft.com/fr-fr/graph/graph-explorer
#
# ###################################################################################################################################################
# todo
#
#   1. clear: encoding for resource.filename vs. os.walk
#   2. recombine object+image+link (shared from iPad)
#   3. recombine image+object+link (shared from Mac)
#
# ###################################################################################################################################################

import json
import requests
import re
import os
import sys
import shutil

from datetime import datetime as dt
from bs4 import BeautifulSoup

# pip3 install pandas
import pandas as pd

from mytools import *

# ###################################################################################################################################################
# CATALOG
# ###################################################################################################################################################

def catalog( token ): 
    myprint( '', line=True, title='GET ONENOTE CATALOG')
    
    url='https://graph.microsoft.com/v1.0/me/onenote/notebooks'

    myprint( '{}'.format( url), prefix='>' )

    try:
        onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + token} ).json()

        if 'error' in onenote_response:
            myprint( '[{0:<8}] error: {1} - {2}'.format(what, onenote_response['error']['code'], onenote_response['error']['message']) )
            return pd.DataFrame()
        else:
            if 'value' not in onenote_response: onenote_catalog = { 'value': [ onenote_response ] }
            else: onenote_catalog = onenote_response

            onenote_catalog = pd.json_normalize(onenote_catalog['value'])[['displayName','self']]
            onenote_catalog.rename( columns={'displayName': 'title', 'self': 'source'}, inplace=True )
            onenote_catalog.drop_duplicates( inplace=True )
            onenote_catalog['what'] = 'onenote'
            onenote_catalog = pd.concat( [ pd.DataFrame( {'title': ['ALL'], 'source': [None], 'what': ['onenote']} ),
                                           onenote_catalog
                                         ], ignore_index=True)

            return onenote_catalog

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...')

        return pd.DataFrame( {'title': ['ALL'], 'source': [None], 'what': ['onenote']} )

# ###################################################################################################################################################
# READ
# ###################################################################################################################################################

def read( directory, token, notebook=None, elements=empty_elements() ): 

    _elements = elements[elements['source'].isin(['onenote'])].copy()
    _elements = empty_elements()
    _files_directory = os.path.join( directory, 'onenote' )

    myprint( elements, 'ONENOTE ELEMENTS' )

    try:
    
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get elements
        # -------------------------------------------------------------------------------------------------------------------------------------------
        #                       https://graph.microsoft.com/v1.0/me/onenote/notebooks
        #                       https://graph.microsoft.com/v1.0/me/onenote/notebooks/{id}
        #                       https://graph.microsoft.com/v1.0/me/onenote/sectionGroups
        # sectionGroupsUrl :    https://graph.microsoft.com/v1.0/me/onenote/notebooks/{id}/sectionGroups
        # sectionGroupsUrl :    https://graph.microsoft.com/v1.0/me/onenote/sectionGroups/{id}/sectionGroups
        #                       https://graph.microsoft.com/v1.0/me/onenote/sections
        # sectionsUrl:          https://graph.microsoft.com/v1.0/me/onenote/notebooks/{id}/sections
        # sectionsUrl:          https://graph.microsoft.com/v1.0/me/onenote/sectionGroups/{id}/sections
        # pagesUrl:             https://graph.microsoft.com/v1.0/me/onenote/sections/{id}/pages

        if len(_elements) == 0:
            myprint( '', line=True, title='GET ONENOTE ELEMENTS')

            def _get( url ):
                onenote = empty_elements()
                run = (url == url)
                page_count = 0
                page_nb = 100
                what = re.search( r'^.*/(.*?)$', url ).group(1)
                myprint( what, prefix="---" )

                while run:
                    if (what == 'pages'): 
                        url += '?$top={}'.format(page_nb)
                        if page_count > 0: url += '&$skip={}'.format(page_count)

                    myprint( '{}'.format( url), prefix='>' )

                    try:
                        onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + token} ).json()

                        if 'error' in onenote_response:
                            myprint( '[{0:<8}] error: {1} - {2}'.format(what, onenote_response['error']['code'], onenote_response['error']['message']) )
                            run = False
                        else:
                            if 'value' not in onenote_response: onenote_objects = { 'value': [ onenote_response ] }
                            else: onenote_objects = onenote_response

                            onenote_objects = pd.json_normalize(onenote_objects['value'])
                            col_list = {}
                            for col in onenote_objects.columns.to_list():
                                col_list[col] = 'onenote_{}'.format(col)
                            onenote_objects.rename( columns=col_list, inplace=True )

                            if len(onenote) >0 : onenote = pd.concat( [ onenote, onenote_objects ], ignore_index=True )
                            else: onenote = onenote_objects.copy()

                            if '@odata.nextLink' in onenote_response:
                                url = onenote_response['@odata.nextLink']
                            else:
                                if (what == 'page'): 
                                    if len(onenote_objects) == 0:
                                        run = False
                                    else:
                                        page_count += len(onenote_objects)
                                        url='https://graph.microsoft.com/v1.0/me/onenote/pages'
                                else:
                                    run = False

                            del onenote_objects
                    except:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        myprint( 'error: {}'.format(exc_obj), prefix='...' )

                onenote.drop_duplicates( inplace=True )

                myprint( '{}: {} elements loaded'.format( what, len(onenote) ), prefix="..." )

                # recursive
                if not what in [ 'pages', 'content']:
                    for u in ['onenote_sectionGroupsUrl', 'onenote_sectionsUrl', 'onenote_pagesUrl']:
                        if u in onenote:
                            cond = ~onenote[u].isna()
                            onenote = pd.concat( [ onenote, onenote[cond][u].apply( lambda x: _get(x) ) ], ignore_index=True )

                return onenote

            # notebooks
            url = notebook if notebook else 'https://graph.microsoft.com/v1.0/me/onenote/notebooks'
            _elements = _get(url)

             # myprint(_elements)

            myprint( 'Nb elements = {}'.format(len(_elements)) )

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get contents
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _get_content( row ):
            myprint( '> [{}] {}'.format( int(row['index']), row['onenote_contentUrl'] ))
            
            try:
                response = requests.get( row['onenote_contentUrl'].replace( "content", "$value"), headers={'Authorization': 'Bearer ' + token} )
                try:
                    iserror = ('error' in response.json())
                except:
                    iserror = False

                if iserror:
                    myprint( 'error: {} - {}'.format(response.json()['error']['code'], response.json()['error']['message']) )
                    return nan
                else:
                    soup = BeautifulSoup(response.text, features="html.parser")
                    return str( soup.body.contents[1] ) if (len(soup.body.contents) > 0) else '<br>'
                    # <br> to avoid empty considered as nan
            except:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                myprint( 'error: {}'.format(exc_obj), prefix='...' )
                return nan

        if 'onenote_contentUrl' in _elements.columns.to_list():
            myprint( '', line=True, title='GET ONENOTE CONTENTS')

            if 'onenote_content' not in _elements.columns.to_list():
                _elements['onenote_content'] = nan

            # process elements with contentUrl and no content
            cond = (~_elements['onenote_contentUrl'].isna())
            cond &= (_elements['onenote_content'].isna())
            nb = len(_elements[cond])

            myprint( 'Recovering {} contents'. format(nb))

            _elements['index'] = nan
            _elements.loc[cond, 'index'] = range(nb, 0, -1)
            _elements.loc[cond, 'onenote_content'] = _elements[cond].apply(_get_content, axis='columns')
            _elements.drop( columns=['index'], inplace=True)

            cond = (~_elements['onenote_contentUrl'].isna())
            cond &= (_elements['onenote_content'].isna())

            if len(_elements[cond]) > 0: myprint( '.. missing {} contents out of {}'. format(len(_elements[cond]), nb))

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _get_resource( row ):

            soup = BeautifulSoup(row['onenote_content'], features="html.parser")

            resources = []

            empty = empty_resource()

            empty['parent'] = row['onenote_id']
            if ('onenote_createdDateTime' in row) and (row['onenote_createdDateTime'] == row['onenote_createdDateTime']): 
                empty['date']  = row['onenote_createdDateTime']
            if ('onenote_lastModifiedDateTime' in row) and (row['onenote_lastModifiedDateTime'] == row['onenote_lastModifiedDateTime']): 
                empty['date']  = row['onenote_lastModifiedDateTime']
            
            # objects
            # -------
            # <object 
            # data="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-8a9f130df6d87945a8099be6b6d2be82!1-34CFFB16AE39C6B3!335924/$value" 
            # data-attachment="SEJOUR BURAIS 007-IND-M-22.pdf" 
            # type="application/pdf">
            # </object>

            for tag in soup.select("object[data-attachment]"): 
                resource = dict(empty)
                resource['name'] = re.search( r'^.*resources/(.*?)!', tag['data']).group(1) + '_' + tag['data-attachment']
                resource['name'] = tag['data-attachment']
                resource['url'] = tag['data']
                resource['type'] = 'object'

                resources += [ resource ]

            # images
            # ------
            # <img 
            # alt="bla bla bla"
            # data-fullres-src="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value" 
            # data-fullres-src-type="image/png" 
            # data-id="2f8fe6dc-10b8-c046-ba5b-c6ccf2c8884a" 
            # data-index="2" 
            # data-options="printout" 
            # data-src-type="image/png" 
            # height="842" 
            # src="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value" 
            # width="595"
            # />

            for tag in soup.select('img[src]'):
                resource = dict(empty)
                resource['name'] = re.search( r'^.*resources/(.*?)!', tag['src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
                resource['url'] = tag['src']
                resource['type'] = 'image'

                resources += [ resource ]

                resource = dict(empty)
                resource['name'] = re.search( r'^.*resources/(.*?)!', tag['data-fullres-src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
                resource['url'] = tag['data-fullres-src']
                resource['type'] = 'fullres'

                resources += [ resource ]

            for resource in resources:
                path = resource['parent'].split('!')
                path.reverse()
                resource['filename'] = os.path.join( _files_directory, 
                                                    os.path.sep.join(path),
                                                    resource['name'] )


            return json.dumps( resources )

            #if len(resources) > 0: return json.dumps( resources )
            #else: return nan

        if 'onenote_content' in _elements.columns.to_list():
            myprint( '', line=True, title='GET ONENOTE RESOURCES')
            
            if 'onenote_attachments' not in _elements:
                _elements['onenote_attachments'] = nan

            cond = (~_elements['onenote_content'].isna())
            cond &= (_elements['onenote_attachments'].isna())

            myprint( 'Processing {} attachments out of {} contents'. format( len(_elements[cond]), 
                                                                             len(_elements[(~_elements['onenote_content'].isna())])))

            _elements.loc[cond, 'onenote_attachments'] = _elements[cond].apply(_get_resource, axis='columns')

            cond = (~_elements['onenote_content'].isna())
            cond &= (_elements['onenote_attachments'].isna())

            if len(_elements[cond]) > 0: myprint( 'missing {} attachments'. format(len(_elements[cond])), prefix="...")

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # set parent
        # -------------------------------------------------------------------------------------------------------------------------------------------

        myprint( '', line=True, title='SET ONENOTE PARENT' )

        _elements['onenote_parent'] = nan

        if 'onenote_parentNotebook.id' in _elements.columns.to_list():
            _elements.loc[~_elements['onenote_parentNotebook.id'].isna(), 'onenote_parent'] = _elements['onenote_parentNotebook.id']
        if 'onenote_parentSectionGroup.id' in _elements.columns.to_list():
            _elements.loc[~_elements['onenote_parentSectionGroup.id'].isna(), 'onenote_parent'] = _elements['onenote_parentSectionGroup.id']
        if 'onenote_parentSection.id' in _elements.columns.to_list():
            _elements.loc[~_elements['onenote_parentSection.id'].isna(), 'onenote_parent'] = _elements['onenote_parentSection.id']

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # reorganize elements
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # merge elements

        myprint( '', line=True, title='REORGANIZE ONENOTE ELEMENTS' )

        def _find_page( row ):
            cond = (_elements['onenote_self'].str.contains("/pages/"))
            cond &= (_elements['tmp_name'].isin([row['tmp_name']]))
            cond &= (_elements['onenote_parent'].isin([row['onenote_id']]))
            found_pages = _elements[cond]
            if len(found_pages) > 0:
                # it is a match
                for index, found_page in found_pages.iterrows():
                    if found_page['onenote_content'] == found_page['onenote_content']: 
                        if row['onenote_content'] != row['onenote_content']: row['onenote_content'] = found_page['onenote_content']
                        else: row['onenote_content'] += found_page['onenote_content']
                    if found_page['onenote_attachments'] == found_page['onenote_attachments']: 
                        if row['onenote_attachments'] != row['onenote_attachments']: row['onenote_attachments'] = found_page['onenote_attachments']
                        else: row['onenote_attachments'] = json.dumps( json.loads(row['onenote_attachments']) + json.loads(found_page['onenote_attachments']) )
                row['tmp_found'] = found_pages['onenote_id'].to_list()
            return row

        _elements['tmp_name'] = nan
        if 'onenote_displayName' in _elements.columns.to_list():
            _elements['tmp_name'] = _elements['onenote_displayName']
        if 'onenote_title' in _elements.columns.to_list():
            cond = ~_elements['onenote_title'].isna()
            cond &= _elements['tmp_name'].isna()
            _elements.loc[cond, 'tmp_name'] = _elements['onenote_title']

        cond = (~_elements['onenote_self'].str.contains("/pages/"))
        _elements['tmp_found'] = nan
        _elements[cond] = _elements[cond].apply(_find_page, axis='columns')

        cond = (~_elements['tmp_found'].isna())
        myprint( 'merged {} contents'. format(len(_elements[cond])), prefix="...")

        _elements['onenote_merged'] = False
        pages = list(dict.fromkeys([x for xs in _elements[cond]['tmp_found'].drop_duplicates().to_list() for x in xs]))
        cond = (_elements['onenote_id'].isin(pages))
        _elements.loc[cond, 'onenote_merged'] = True

        _elements.drop( columns=['tmp_found', 'tmp_name'], inplace=True)

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # load resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _load_resource( resource ):

            if not resource['filename']:
                myprint("[{}] no filename for {}".format(resource['index'], resource['url']), prefix='  ...')
                return resource

            # test dates to check if load is mandatory
            date_page = resource['date']
            try:
                date_page = dt.strptime(date_page, '%Y-%m-%dT%H:%M:%S.%fZ')
            except:
                date_page = dt.strptime(date_page, '%Y-%m-%dT%H:%M:%SZ')

            try:
                date_file = dt.fromtimestamp(os.path.getmtime( resource['filename'] ))
            except:
                date_file = date_page

            # load file
            if not os.path.isfile(resource['filename']) or (date_file < date_page):

                myprint( '[{}] {}...'.format(resource['index'], resource['url'].replace('$value', 'content')), prefix='>')

                if not os.path.isfile(resource['filename']): myprint( 'missing file', prefix='...' )
                elif (date_file < date_page): myprint( 'outdated file', prefix='...' )

                out_dir = os.path.dirname(resource['filename'])

                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)

                try:
                    data =  requests.get( resource['url'].replace('$value', 'content'), headers={'Authorization': 'Bearer ' + token} )
                    try:
                        iserror = ('error' in data.json())
                        if iserror:
                            myprint( 'error: {} - {}'.format(data.json()['error']['code'], data.json()['error']['message']) )
                    except:
                        iserror = False
                        with open(resource['filename'], 'wb') as fs:
                            fs.write(data.content) 

                        myprint( '[{}] {}: {} bytes'.format( resource['index'], 
                                                                resource['filename'], 
                                                                os.path.getsize(resource['filename']) ), 
                                    prefix='...' )

                        resource['processed'] = True
                except:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    myprint( 'error: {}'.format(exc_obj), prefix='...' )
            else:
                    resource['processed'] = True

            return resource

        cond = (~_elements['onenote_attachments'].isna())
        resources = _elements[cond]['onenote_attachments'].apply( lambda x: json.loads(x) )
        if len(resources) > 0: 
            myprint( '', line=True, title='LOAD ONENOTE RESOURCES')

            resources = resources.apply(pd.Series).stack().reset_index(drop=True).apply(pd.Series)

            nb = len(resources)
            myprint( 'Processing {} resources'. format(nb))
            resources['index'] = range(nb, 0, -1)        
            resources['processed'] = False       
            
            if len(resources) > 0: 
                resources = resources.apply(_load_resource, axis='columns')

            myprint( '.. missing {} resources out of {}'. format(len(resources[resources['processed']==False]), nb))

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # set body
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _body( element ):
            if element['onenote_content'] and (element['onenote_content'] == element['onenote_content']):

                soup = BeautifulSoup( '<body>' + element['onenote_content'] + '</body>', features="html.parser" )

                # absolute
                # --------
                # <body data-absolute-enabled="true" style="font-family:Calibri;font-size:11pt">
                # <div style="position:absolute;left:48px;top:115px;width:576px">

                for tag in soup.select("body[data-absolute-enabled]"):
                    del tag["data-absolute-enabled"]

                tags = soup.find_all( 'div', style=re.compile("position:absolute") )
                for tag in tags:
                    if (tag["style"].find("position:absolute") != -1):
                        del tag["style"]

                # resize images

                tags = soup.find_all( 'img' )
                for tag in tags:
                    del tag['width']
                    del tag['height']

                    tag['width'] = 1000

                # resize objects

                tags = soup.find_all( 'object' )
                for tag in tags:
                    del tag['width']
                    del tag['height']

                    tag['width'] = 1000

                # stripped

                if len(soup.body.contents) > 0:
                    element['body'] = str( soup.body.contents[0] )
                
                # resources

                # replace url by file
                if element['onenote_attachments'] == element['onenote_attachments']:
                    for resource in json.loads(element['onenote_attachments']):
                        if resource['filename']:
                            element['body'] = element['body'].replace( resource['url'], 
                                                                    resource['filename'].replace( directory, 'static' )
                                                                    )

            return element

        if 'onenote_content' in _elements.columns.to_list():
            myprint( '', line=True, title='SET ONENOTE BODY')

            cond = (~_elements['onenote_content'].isna())
            _elements['body'] = nan
            _elements.loc[cond, 'body'] = _elements[cond].apply( _body, axis='columns' )
        
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # normalize
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # normalized ['source','what','type','id','title','created','modified','author','parent','childs','body','path','slug','resources']

        myprint( '', line=True, title='NORMALIZE ONENOTE')

        _elements['source'] = 'onenote'

        # self="https://graph.microsoft.com/v1.0/users/laurent@burais.fr/onenote/notebooks/0-34CFFB16AE39C6B3!335711"
        if 'onenote_self' in _elements.columns.to_list():
            def _what( text ):
                return re.search( r'^.*onenote/(.*?)/', text).group(1)
            _elements['what'] = _elements['onenote_self'].apply( lambda x: re.search( r'^.*onenote/(.*?)/', x).group(1) )

        _elements['type'] = 'post' 
        _elements.loc[_elements['type'].isin(['pages']), 'type'] = 'page' 

        # id
        if 'onenote_id' in _elements.columns.to_list(): _elements['id'] = _elements['onenote_id']

        # title
        if 'onenote_title' in _elements.columns.to_list(): _elements['title'] = _elements['onenote_title']
        if 'onenote_displayName' in _elements.columns.to_list(): _elements.loc[_elements['title'].isna(), 'title'] = _elements['onenote_displayName']

        # dates
        if 'onenote_createdDateTime' in _elements.columns.to_list(): _elements['created'] = _elements['onenote_createdDateTime']
        if 'onenote_lastModifiedDateTime' in _elements.columns.to_list(): _elements['modified'] = _elements['onenote_lastModifiedDateTime']

        # author
        for col in ['onenote_createdBy.user.displayName', 'onenote_lastModifiedBy.user.displayName']:
            if col in _elements.columns.to_list(): 
                _elements.loc[~_elements[col].isna(), 'authors'] = _elements[col]

        # parent
        _elements['parent'] = _elements['onenote_parent']

        # childs
        def _set_childs( element ):
            childs = _elements[_elements['parent'] == element['id'] ]['id']
            if len(childs) > 0: return childs.to_list()
            else: return nan
        _elements['childs'] = _elements.apply( _set_childs, axis='columns' )

        # body
        # _elements['body'] set above

        # path
        # _elements['path'] 

        # resources
        _elements['resources'] = _elements['onenote_attachments']

        # slug
        _elements['slug'] = _elements['id'].apply( lambda x: slugify(x) )

        # drop columns

        #_elements.drop( columns=[ 'onenote_attachments', 'onenote_parent' ], inplace=True )

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # save excel
        # -------------------------------------------------------------------------------------------------------------------------------------------

        save_excel(directory, _elements, 'onenote')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # completed
        # -------------------------------------------------------------------------------------------------------------------------------------------

        return _elements

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...')

        return empty_elements()

# ###################################################################################################################################################
# WRITE
# ###################################################################################################################################################

def write( directory, token, elements=empty_elements() ): 

    pass

# ###################################################################################################################################################
# CLEAR
# ###################################################################################################################################################

def clear( directory, elements=empty_elements(), all=False ): 

    myprint( '', line=True, title='CLEAR ONENOTE FILES')

    _directory = os.path.join( directory, 'onenote' )

    if all:
        if os.path.isdir(_directory):
            myprint( 'Removing {}...'.format(_directory), prefix='>' )
            shutil.rmtree(_directory)
            os.makedirs(_directory)
    else:
        cond = (~elements['resources'].isna())
        cond &= elements['source'].isin(['onenote'])
        resources = elements[cond]['resources'].apply( lambda x: json.loads(x) )

        if len(resources) > 0: 
            resources = resources.apply(pd.Series).stack().reset_index(drop=True).apply(pd.Series)
            resources = resources['filename'].drop_duplicates()

            myprint( 'Processing {} resources'. format(len(resources)))

            onenote_files = list(dict.fromkeys(resources.to_list()))

            count = 0
            removed = 0
            for root, dirs, files in os.walk(_directory):
                for name in files:
                    if not (os.path.join(root, name) in onenote_files):
                        removed += 1
                        myprint('[{}] removing {} file'.format(removed, os.path.join(root, name)), prefix='>')
                        #os.remove( os.path.join(root, name) )
                    count += 1

            for root, dirs, files in os.walk(_directory, topdown=False):
                for name in dirs:
                    walk = sum([len(files) for r, d, files in os.walk(os.path.join(root, name))])
                    if walk == 0:
                        myprint('removing {} directory'.format(os.path.join(root, name)), prefix='>')
                        #shutil.rmtree(os.path.join(root, name))

            myprint('removed {} out of {} files'.format(removed, count), prefix='...')

