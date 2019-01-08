#!/usr/bin/env python

"""Figshare helper
   Based on https://docs.figshare.com/#upload_files_example_upload_on_figshare
"""

import hashlib
import json
import os
import argparse

import requests
from requests.exceptions import HTTPError


BASE_URL = 'https://api.figshare.com/v2/{endpoint}'
CHUNK_SIZE = 1048576

# arguments
parser = argparse.ArgumentParser(description='Manage files on figshare.')
parser.add_argument("--authtoken", help="Your Auth Token from Figshare", required=True)
parser.add_argument("--project", help="Existing Project ID to use", type=int)
parser.add_argument("--article", help="Existing Article ID to use", type=int)
parser.add_argument("--filepath", help="Path to file or directory of files to upload to an article")
parser.add_argument("--title", help="Title for new article")
parser.add_argument("--action", help="Type of action to perform", required=True, choices=['create', 'upload', 'delete'])

args = parser.parse_args()


def raw_issue_request(method, url, data=None, binary=False):
    headers = {'Authorization': 'token ' + args.authtoken}
    if data is not None and not binary:
        data = json.dumps(data)
    response = requests.request(method, url, headers=headers, data=data)
    try:
        response.raise_for_status()
        try:
            data = json.loads(response.content)
        except ValueError:
            data = response.content
    except HTTPError as error:
        print 'Caught an HTTPError: {}'.format(error.message)
        print 'Body:\n', response.content
        raise

    return data


def issue_request(method, endpoint, *args, **kwargs):
    return raw_issue_request(method, BASE_URL.format(endpoint=endpoint), *args, **kwargs)


def list_articles():
    result = issue_request('GET', 'account/articles')
    print 'Listing current articles:'
    if result:
        for item in result:
            print u'  {url} - {title}'.format(**item)
    else:
        print '  No articles.'
    print


def create_article(title):
    data = {
        'title': title  # You may add any other information about the article here as you wish.
    }
    result = issue_request('POST', 'account/articles', data=data)
    print 'Created article:', result['location'], '\n'

    result = raw_issue_request('GET', result['location'])

    return result['id']


def list_files_of_article(article_id):
    result = issue_request('GET', 'account/articles/{}/files'.format(article_id))
    print 'Listing files for article {}:'.format(article_id)
    if result:
        for item in result:
            print '  {id} - {name}'.format(**item)
    else:
        print '  No files.'

    print


def delete_files_of_article(article_id):
    result = issue_request('GET', 'account/articles/{}/files'.format(article_id))
    print 'Deleting files for article {}:'.format(article_id)
    if result:
        for item in result:
            del_result = issue_request('DELETE', 'account/articles/{}/files/{id}'.format(article_id, **item))
    else:
        print '  No files to delete'

    print


def get_file_check_data(file_name):
    with open(file_name, 'rb') as fin:
        md5 = hashlib.md5()
        size = 0
        data = fin.read(CHUNK_SIZE)
        while data:
            size += len(data)
            md5.update(data)
            data = fin.read(CHUNK_SIZE)
        return md5.hexdigest(), size


def initiate_new_upload(article_id, file_name):
    endpoint = 'account/articles/{}/files'
    endpoint = endpoint.format(article_id)

    md5, size = get_file_check_data(file_name)
    data = {'name': os.path.basename(file_name),
            'md5': md5,
            'size': size}

    result = issue_request('POST', endpoint, data=data)
    print 'Initiated file upload:', result['location'], '\n'

    result = raw_issue_request('GET', result['location'])

    return result


def complete_upload(article_id, file_id):
    issue_request('POST', 'account/articles/{}/files/{}'.format(article_id, file_id))


def upload_parts(file_info, file_path):
    url = '{upload_url}'.format(**file_info)
    result = raw_issue_request('GET', url)

    print 'Uploading parts:'
    with open(file_path, 'rb') as fin:
        for part in result['parts']:
            upload_part(file_info, fin, part)
    print


def upload_part(file_info, stream, part):
    udata = file_info.copy()
    udata.update(part)
    url = '{upload_url}/{partNo}'.format(**udata)

    stream.seek(part['startOffset'])
    data = stream.read(part['endOffset'] - part['startOffset'] + 1)

    raw_issue_request('PUT', url, data=data, binary=True)
    print '  Uploaded part {partNo} from {startOffset} to {endOffset}'.format(**part)


def main():


    # Create a new article (aka Fileset) and upload files to it
    if args.action == 'create':
        # We first create the article
        new_article_id = create_article(args.title)

        # Then we upload the file(s)
        for root, dirs, files in os.walk(args.filepath):
            for filename in files:
                file_info = initiate_new_upload(new_article_id, os.path.join(root, filename))
                # Until here we used the figshare API; following lines use the figshare upload service API.
                upload_parts(file_info, os.path.join(root, filename))
                # We return to the figshare API to complete the file upload process.
                complete_upload(args.article, file_info['id'])
    
        list_files_of_article(args.article)


    # Upload files to an existing article
    if args.action == 'upload':
        for root, dirs, files in os.walk(args.filepath):
            for filename in files:
                file_info = initiate_new_upload(args.article, os.path.join(root, filename))
        # Until here we used the figshare API; following lines use the figshare upload service API.
                upload_parts(file_info, os.path.join(root, filename))
        # We return to the figshare API to complete the file upload process.
                complete_upload(args.article, file_info['id'])
    
        list_files_of_article(args.article)
    
    # Delete files from an existing article
    if args.action == 'delete':
        delete_files_of_article(args.article)
  

if __name__ == '__main__':
    main()

