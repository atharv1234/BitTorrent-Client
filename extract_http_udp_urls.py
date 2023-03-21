import sys
from collections import OrderedDict 
import bencodepy
from beautifultable import BeautifulTable
import random as rd


    
 
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
        torrent_file_table.columns.header = ["Torrent Headers", "Extracted info"]
        
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
           
            


class torrent_tracker():

    #Get the http and udp trackers url seperately
    def __init__(self, torrent):
        # the responding tracker instance for client
        self.client_tracker = None
        
        # connection status of the trackers
        self.connection_success         = 1 
        self.connection_failure         = 2
        self.connection_not_attempted   = 3

        # get all the trackers list of the torrent data
        self.trackers_list = []
        self.httpTrackers = []
        self.udpTrackers = []
        for tracker_url in torrent.torrent_metadata.trackers_urlList:
            #classify HTTP and UDP torrent trackers
            if 'http' in tracker_url[:4]:
                self.httpTrackers.append(tracker_url)
            if 'udp' in tracker_url[:4]:
                self.udpTrackers.append(tracker_url) 
            # append the tracker class instance 
            self.trackers_list.append(tracker_url)


        print("-----HTTP tracker urls-----\n",self.httpTrackers)
        print("-----UDP tracker urls-----\n",self.udpTrackers)
    



class bittorrent_client():
    #Reads the torrent file and creates torrent class object
    def __init__(self, path):
        # extract the torrent file path 
        torrent_file_path = path

        # read metadata from the torrent torrent file 
        self.torrent_info = torrent_file_reader(torrent_file_path)
        print(self.torrent_info)

        # decide whether the user want to download or seed the torrent
        self.client_request = { 'downloading': None, 'seeding': None}
        self.client_request['downloading'] = torrent_file_path                       
        # make torrent class instance from torrent data extracted from torrent file
        self.torrent = torrent(self.torrent_info.get_data(), self.client_request)
        print(self.torrent)
        
#This function will contact the trackers in further developments
   
    def contact_trackers(self):

        # get list of torrent tracker object from torrent file
        self.trackers_list = torrent_tracker(self.torrent)
         
        








class torrent():

    def __init__(self, torrent_metadata, client_request):
        # store the orginal metadata extracted from the file
        self.torrent_metadata   = torrent_metadata
        self.client_request     = client_request
        # pieces divided into chunks of fixed block size #16KB
        self.block_length   = 16 * (2 ** 10) 
        
        # piece length of torrent file
        self.pieceLength = torrent_metadata.pieceLength


        # the count of the number pieces that the files is made of
        self.count_of_pieces = int(len(self.torrent_metadata.pieces) / 20)

        # peer id encoded with azureus style encoding
        self.peer_id = ('-BC0451-' + ''.join([str(rd.randint(0, 9)) for i in range(12)])).encode()
    
    
    def __str__(self):
        column_header =  'Data of client torrent\n (State of client = '
        if self.client_request['downloading'] != None:
            column_header += 'downloading)\n'
        if self.client_request['seeding'] != None:
            column_header += 'seeding)\n'
        
        torrent_file_table = BeautifulTable()
        torrent_file_table.columns.header = [column_header, "DATA VALUE"]
        
        # file name
        torrent_file_table.rows.append(['File name', str(self.torrent_metadata.fileName)])
        # file size
        torrent_file_table.rows.append(['File size', str(round(self.torrent_metadata.fileSize / (2 ** 20), 2)) + ' MB'])
        # piece length 
        torrent_file_table.rows.append(['Piece length', str(self.torrent_metadata.pieceLength)])
        # files (multiple file torrents)
        if self.torrent_metadata.files:
            torrent_file_table.rows.append(['Files', str(len(self.torrent_metadata.files))])
        else:
            torrent_file_table.rows.append(['Files', str(self.torrent_metadata.files)])
        # number of pieces in file 
        torrent_file_table.rows.append(['Number of Pieces', str(self.count_of_pieces)])
        #client peer id
        torrent_file_table.rows.append(['Client peer ID', str(self.peer_id)])
        
        return str(torrent_file_table)



path = sys.argv[1]
client = bittorrent_client(path)
client.contact_trackers()