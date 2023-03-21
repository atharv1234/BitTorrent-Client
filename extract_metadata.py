#Mudit Bapna
#Atharv Terwadkar

import sys
from collections import OrderedDict 
import bencodepy
from beautifultable import BeautifulTable
file=sys.argv[1]
    
 
 
#metadata from the torrent file 
class torrent_info():
    def __init__(self, trackers_urlList, fileName, fileSize, pieceLength, pieces, files):
        self.trackers_urlList  = trackers_urlList     
        self.fileName = fileName                  
        self.fileSize = fileSize                 
        self.pieceLength = pieceLength              
        self.pieces = pieces                    
        self.files = files                     


#torrent_info class is inherited
class torrent_file_reader(torrent_info):
    
    def __init__(self, torrent_file_path):
        try :
            # raw data from the torrent file 
            self.torrent_file_RawInfo_extract = bencodepy.decode_from_file(torrent_file_path)
        except Exception as err:
            sys.exit()
        
        self.encoding = 'UTF-8'
        
        # getting data in readable format
        self.torrent_info_extract = self.extract_torrent_info(self.torrent_file_RawInfo_extract)
        
        # list of trackers 
        if 'announce-list' in self.torrent_info_extract.keys():
            trackers_urlList = self.torrent_info_extract['announce-list'] 
        else:
            trackers_urlList = [self.torrent_info_extract['announce']]
        
        # file name 
        fileName = self.torrent_info_extract['info']['name']
        # piece length in bytes
        pieceLength = self.torrent_info_extract['info']['piece length']
        pieces = self.torrent_info_extract['info']['pieces']
            
        # files is list of tuple of size and path in case of multifile torrent
        files = None

        # check if torrent file contains multiple paths 
        if 'files' in self.torrent_info_extract['info'].keys():
            # file information - (length, path)
            files_list = self.torrent_info_extract['info']['files']
            files = [(file_data['length'], file_data['path']) for file_data in files_list]
            fileSize = 0
            for file_length, file_path in files:
                fileSize += file_length
        else : 
            # file size in bytes 
            fileSize = self.torrent_info_extract['info']['length']
       
        # base class constructor 
        super().__init__(trackers_urlList, fileName, fileSize, pieceLength, pieces, files)

    def extract_torrent_info(self, file):
        # torrent metadata is ordered dictionary 
        torrent_extract = OrderedDict()
        
        # extract all the key values pair in raw data and decode them
        for key, value in file.items():
            # decoding the key
            new_key = key.decode(self.encoding)
            # if type of value is of type dictionary then do deep copying
            if type(value) == OrderedDict:
                torrent_extract[new_key] = self.extract_torrent_info(value)
            # if the current torrent file could have multiple files with paths
            elif type(value) == list and new_key == 'files': #list of ordered dict.
                
                torrent_extract[new_key] = list(map(lambda x : self.extract_torrent_info(x), value))
            elif type(value) == list and new_key == 'path': #list of string
                #For eg consider we have a list  l1=[" element"] but we want element as a string then we write l1[0]
                torrent_extract[new_key] = value[0].decode(self.encoding) 
            # url list parameter
            elif type(value) == list and new_key == 'url-list' or new_key == 'collections':
                torrent_extract[new_key] = list(map(lambda x : x.decode(self.encoding), value))
            # if type of value is of type list
            elif type(value) == list :
                    torrent_extract[new_key] = list(map(lambda x : x[0].decode(self.encoding), value))
            # if type of value if of types byte
            elif type(value) == bytes and new_key != 'pieces':
                #The top level dictionary
                torrent_extract[new_key] = value.decode(self.encoding)
            else :
                torrent_extract[new_key] = value

        # torrent extracted metadata
        return torrent_extract

    # return the torrent instance 
    def get_data(self):
        return torrent_info(self.trackers_urlList, self.fileName, 
                                self.fileSize,         self.pieceLength,      
                                self.pieces,             self.files)

    # provides torrent file full information

    def __str__(self):
        torrent_file_table = BeautifulTable()
        torrent_file_table.columns.header = ["TORRENT FILE HEADERS", "INFO EXTRACTED"]
        
        tracker_urls = self.trackers_urlList[0]
        if len(self.trackers_urlList) < 3:
            for tracker_url in self.trackers_urlList[1:]:
                tracker_urls += '\n' + tracker_url 
        else:
            tracker_urls += '\n... ' 
            tracker_urls += str(len(self.trackers_urlList)-1) + ' more tracker urls !' 
        
        # tracker urls
        torrent_file_table.rows.append(['Tracker List', tracker_urls])
        # file name
        torrent_file_table.rows.append(['File name', str(self.fileName)])
        # file size
        torrent_file_table.rows.append(['File size', str(self.fileSize) + ' B'])
        # piece length 
        torrent_file_table.rows.append(['Piece length', str(self.pieceLength) + ' B'])
        # files (multiple file torrents)
        if self.files:
            torrent_file_table.rows.append(['Files', str(len(self.files))])
        else:
            torrent_file_table.rows.append(['Files', str(self.files)])
        return str(torrent_file_table)
           
            
torrent_info = torrent_file_reader(file)
print(torrent_info)
