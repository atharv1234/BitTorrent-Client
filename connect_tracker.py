import sys
from collections import OrderedDict 
import bencodepy
import requests
from socket import *
import struct
from beautifultable import BeautifulTable
import hashlib
import random as rd

from connect_peer import swarm
from common_file_handler import *

    
 
#metadata from the torrent file
class torrent_info():
    def __init__(self, trackers_urlList, fileName, fileSize, pieceLength, info_hash, pieces, files):
        self.trackers_urlList  = trackers_urlList     
        self.fileName = fileName                  
        self.fileSize = fileSize                 
        self.pieceLength = pieceLength  
        self.info_hash = info_hash            
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
        
        if b'encoding' in self.torrent_file_RawInfo_extract.keys():
            self.encoding = self.torrent_file_RawInfo_extract[b'encoding'].decode()
        else:
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
        # info hash generated for trackers
        info_hash    = self.generate_info_hash() 
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
        super().__init__(trackers_urlList, fileName, fileSize, pieceLength,info_hash, pieces, files)

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
                try:
                    torrent_extract[new_key] = list(map(lambda x : x[0].decode(self.encoding), value))
                except:
                    torrent_extract[new_key] = value
            # if type of value if of types byte
            elif type(value) == bytes and new_key != 'pieces':
                #The top level dictionary
                try:
                    torrent_extract[new_key] = value.decode(self.encoding)
                except:
                    torrent_extract[new_key] = value
            else :
                torrent_extract[new_key] = value

        # torrent extracted metadata
        return torrent_extract

    # info_hash from the torrent file
    def generate_info_hash(self):
        sha1_hash = hashlib.sha1()
        # get the raw info value
        raw_info = self.torrent_file_RawInfo_extract[b'info']
        # update the sha1 hash value
        sha1_hash.update(bencodepy.encode(raw_info))
        return sha1_hash.digest()
        
    # return the torrent instance 
    def get_data(self):
        return torrent_info(self.trackers_urlList, self.fileName, 
                                self.fileSize,         self.pieceLength,
                                self.info_hash,      
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
           
            
class tracker_data():
    # contructs the tracker request data 
    def __init__(self, torrent):
        self.compact = 1
        # the request parameters of the torrent 
        self.request_parameters = {
            'info_hash' : torrent.torrent_metadata.info_hash,
            'peer_id'   : torrent.peer_id,
            'port'      : torrent.client_port,
            'uploaded'  : torrent.statistics.num_pieces_uploaded,
            'downloaded': torrent.statistics.num_pieces_downloaded,
            'left'      : torrent.statistics.num_pieces_left,
            'compact'   : self.compact
        }
        self.interval   = None
        self.complete   = None
        self.incomplete = None
        self.peers_list = [] 




    #Class HTTP torrent tracker helps the client communicate to any HTTP torrent tracker. 

class http_torrent_tracker(tracker_data):
    
    # contructor : initializes the torrent information
    def __init__(self, torrent, tracker_url):
        super().__init__(torrent)
        self.tracker_url = tracker_url

    # attempts to connect to HTTP tracker
    # returns true if conncetion is established false otherwise
    def get_torrent_info(self):
        # try establishing a connection to the tracker
        try:
            # the reponse from HTTP tracker is an bencoded dictionary  
            print("Before bencode response",self.tracker_url)
            bencoded_response = requests.get(self.tracker_url,self.request_parameters,timeout=5)
            
            # decode the bencoded dictionary to python ordered dictionary 
            raw_response_dict = bencodepy.decode(bencoded_response.content)
            print(raw_response_dict)
            # parse the dictionary containing raw data
            self.parse_http_tracker_response(raw_response_dict)
            return True
        except Exception as error_msg:
            # cannont establish a connection with the tracker
            return False

    # extract the important information for the HTTP response dictionary 
    def parse_http_tracker_response(self, raw_response_dict):
        
        # interval : specifies minimum time client show wait for sending next request 
        if b'interval' in raw_response_dict:
            self.interval = raw_response_dict[b'interval']

        # list of peers form the participating the torrent
        if b'peers' in raw_response_dict:
            self.peers_list = []
            # extract the raw peers data 
            raw_peers_data = raw_response_dict[b'peers']
            print("jj")
            # create a list of each peer information which is of 6 bytes
            raw_peers_list = [raw_peers_data[i : 6 + i] for i in range(0, len(raw_peers_data), 6)]
            print("PEERS LIST",raw_peers_list)
            # extract all the peer id, peer IP and peer port
            for raw_peer_data in raw_peers_list:
                # extract the peer IP address
                print("IP",raw_peer_data[0:4]) 
                peer_IP = ".".join(str(int(a)) for a in raw_peer_data[0:4])
                
                # extract the peer port number
                peer_port = raw_peer_data[4] * 256 + raw_peer_data[5]
                # append the (peer IP, peer port)
                self.peers_list.append((peer_IP, peer_port))
                print(self.peers_list)
            
        # number of peers with the entire file aka seeders
        if b'complete' in raw_response_dict:
            self.complete = raw_response_dict[b'complete']

        # number of non-seeder peers, aka "leechers"
        if b'incomplete' in raw_response_dict:
            self.incomplete = raw_response_dict[b'incomplete']
        
        # tracker id must be sent back by the user on announcement
        if b'tracker id' in raw_response_dict:
            self.tracker_id = raw_response_dict[b'tracker id']

    def get_peers_data(self):
        peer_data = {'interval' : self.interval, 'peers' : self.peers_list,
                        'leechers' : self.incomplete, 'seeders'  : self.complete}
        
        return peer_data
            
class udp_torrent_tracker(tracker_data):
    
    # contructor : initializes the torrent information
    def __init__(self, torrent, tracker_url):
        super().__init__(torrent)
        # extract the tracker hostname and tracker port number
        self.tracker_url, self.tracker_port = self.parse_udp_tracker_url(tracker_url)
        
        # connection id -> initially a specific number
        self.connection_id = 0x41727101980                    
        # action -> initially set to connection request action
        self.action = 0x0                                            
        # transaction id : random id by client
        self.transaction_id = int(rd.randrange(0, 255))          
        
    
    # the function returns (hostname, port) from url
    def parse_udp_tracker_url(self, tracker_url):
        #udp://tracker.coppersurfer.tk:6969/announce
        domain_url = tracker_url[6:].split(':')    #--> ['tracker.coppersurfer.tk','6969/announce']
        udp_tracker_url = domain_url[0]            #-->tracker.coppersurfer.tk
        udp_tracker_port = int(domain_url[1].split('/')[0])   #--> 6969
        return (udp_tracker_url, udp_tracker_port)


    # attempts to connect to UDP tracker
    # returns true if conncetion is established false otherwise
    def get_torrent_info(self):

        self.tracker_sock = socket(AF_INET, SOCK_DGRAM) 
        self.tracker_sock.settimeout(5)

        # connection message for UDP tracker connection request
        connection_msg = self.build_connection_msg()
        
        # attempt connecting and announcing the UDP tracker
        try:
            # get the connection id from the connection request 
            self.connection_id = self.udp_connection_request(connection_msg)
            # annouce msg for UDP tracker 
            announce_msg = self.build_announce_msg()
            self.raw_announce_reponse = self.udp_announce_request(announce_msg)
            # get the peers IP, peer port from the announce response
            self.parse_udp_tracker_response(self.raw_announce_reponse)
        
            self.tracker_sock.close()
            
            if self.peers_list and len(self.peers_list) != 0:
                return True
            else:
                return False
        except Exception as error_msg:
            print(error_msg)
            self.tracker_sock.close()
            return False
            

    # creates the connection msg for the UDP tracker 
    def build_connection_msg(self):
        req_buffer  = struct.pack("!q", self.connection_id) #q =long long int     first 8 bytes : connection_id
        req_buffer += struct.pack("!i", self.action)            # next 4 bytes  : action
        req_buffer += struct.pack("!i", self.transaction_id)    # next 4 bytes  : transaction_id
        return req_buffer


    # recieves the connection reponse from the tracker
    def udp_connection_request(self, connection_msg):
        # send the connection msg to the tracker
        self.tracker_sock.sendto(connection_msg, (self.tracker_url, self.tracker_port))
        # recieve the raw connection data
        try:
            raw_connection_data, conn = self.tracker_sock.recvfrom(2048)
        except :
            raise RuntimeError('UDP tracker connection request failed')
        
        return self.parse_connection_response(raw_connection_data)


    # gets the reponse connection id send by UDP tracker
    def parse_connection_response(self, raw_connection_data):
        # data length cant be less than 16 bytes
        if(len(raw_connection_data) < 16):
            raise RuntimeError('UDP tracker wrong reponse length of connection ID !')
        
        # get the reponse action : first 4 bytes
        response_action = struct.unpack_from("!i", raw_connection_data)[0]       
        # error reponse from tracker 
        if response_action == 0x3:
            error_msg = struct.unpack_from("!s", raw_connection_data, 8)
            raise RuntimeError('UDP tracker reponse error : ' + error_msg)
        
        # get the reponse transaction id : next 4 bytes
        response_transaction_id = struct.unpack_from("!i", raw_connection_data, 4)[0]
        # request and response transaction id should be same
        if(response_transaction_id != self.transaction_id):
            raise RuntimeError('UDP tracker wrong response transaction ID !')
        
        # get the response connection id : next 8 bytes
        reponse_connection_id = struct.unpack_from("!q", raw_connection_data, 8)[0]
        return reponse_connection_id


    # returns the annouce request msg
    def build_announce_msg(self):
        # action = 1 (annouce)
        self.action = 0x1            
        # first 8 bytes connection_id
        announce_msg =  struct.pack("!q", self.connection_id)    
        # next 4 bytes is action
        announce_msg += struct.pack("!i", self.action)  
        # next 4 bytes is transaction id
        announce_msg += struct.pack("!i", self.transaction_id)  
        # next 20 bytes the info hash string of the torrent 
        announce_msg += struct.pack("!20s", self.request_parameters['info_hash'])
        # next 20 bytes the peer_id 
        announce_msg += struct.pack("!20s", self.request_parameters['peer_id'])         
        # next 8 bytes the number of bytes downloaded
        announce_msg += struct.pack("!q", self.request_parameters['downloaded'])
        # next 8 bytes the left bytes
        announce_msg += struct.pack("!q", self.request_parameters['left'])
        # next 8 bytes the number of bytes uploaded 
        announce_msg += struct.pack("!q", self.request_parameters['uploaded']) 
        # event 2 denotes start of downloading
        announce_msg += struct.pack("!i", 0x2) 
        # client's IP address, set this 0 if we want the tracker to use the sender
        announce_msg += struct.pack("!i", 0x0) 
        # some random key
        announce_msg += struct.pack("!i", int(rd.randrange(0, 255)))
        # number of peers require, set this to -1 by defualt
        announce_msg += struct.pack("!i", -1)                   
        # port on which response will be sent 
        announce_msg += struct.pack("!H", self.request_parameters['port'])
        return announce_msg


    # recieves the announce reponse from the tracker
    # trying for seven times
    def udp_announce_request(self, announce_msg):
        raw_announce_data = None
        trails = 0
        while(trails < 7):
            try:
                self.tracker_sock.sendto(announce_msg, (self.tracker_url, self.tracker_port))
                raw_announce_data, conn = self.tracker_sock.recvfrom(2048)
                break
            except:
                print(self.tracker_url + ' failed announce request attempt ' + str(trails + 1))
            trails = trails + 1
        return raw_announce_data

    
    # parses the UDP tracker annouce response 
    def parse_udp_tracker_response(self, raw_announce_reponse):
        if(len(raw_announce_reponse) < 20):
            raise RuntimeError('Invalid response length in announcing!')
        
        # first 4 bytes is action
        response_action = struct.unpack_from("!i", raw_announce_reponse)[0]     
        # next 4 bytes is transaction id
        response_transaction_id = struct.unpack_from("!i", raw_announce_reponse, 4)[0]
        # compare for the transaction id
        if response_transaction_id != self.transaction_id:
            raise RuntimeError('The transaction id in annouce response do not match')
        
        # check if the response contains any error message
        if response_action != 0x1:
            error_msg = struct.unpack_from("!s", raw_announce_reponse, 8)
            raise RuntimeError("Error while annoucing: %s" % error_msg)

        data_index = 8  # first 8 bytes of transaction id and action
        # interval : specifies minimum time client should wait for sending next request 
        self.interval = struct.unpack_from("!i", raw_announce_reponse, data_index)[0]
        
        data_index = data_index + 4
        # leechers : the peers not uploading anything
        self.leechers = struct.unpack_from("!i", raw_announce_reponse, data_index)[0] 
        
        data_index = data_index + 4
        # seeders : the peers uploading the file
        self.seeders = struct.unpack_from("!i", raw_announce_reponse, data_index)[0] 
        
        data_index = data_index + 4
        # obtains the peers list of (peer IP, peer port)
        self.peers_list = []
        while(data_index != len(raw_announce_reponse)):
            # raw data of peer IP, peer port
            raw_peer_data = raw_announce_reponse[data_index : data_index + 6]    

            # get the peer IP address 
            peer_IP = ".".join(str(int(a)) for a in raw_peer_data[0:4])
            print("IP UDP-: ",peer_IP)
            # get the peer port number
            peer_port = raw_peer_data[4] * 256 + raw_peer_data[5]
               
            # append to IP, port tuple to peer list
            self.peers_list.append((peer_IP, peer_port))
            data_index = data_index + 6

    # function for getting the peer data recivied by UDP tracker
    def get_peers_data(self):
        peer_data = {'interval' : self.interval, 'peers' : self.peers_list,
                     'leechers' : self.incomplete, 'seeders'  : self.complete}
        
        return peer_data

    
    # ensure that socket used for tracker request is closed
    def __exit__(self):
        self.tracker_sock.close()

    
    # logs the information obtained by the HTTP tracker 
    def __str__(self):
        tracker_table = BeautifulTable()
        tracker_table.columns.header = ["UDP TRACKER RESPONSE DATA", "DATA VALUE"]
        
        # udp tracker URL
        tracker_table.rows.append(['UDP tracker URL', self.tracker_url])
        # interval 
        tracker_table.rows.append(['Interval', str(self.interval)])
        # number of leeachers
        tracker_table.rows.append(['Number of leechers', str(self.leechers)])
        # number of seeders
        tracker_table.rows.append(['Number of seeders', str(self.seeders)])
        # number of peers recieved
        peer_data  = '(' + self.peers_list[0][0] + ' : '
        peer_data += str(self.peers_list[0][1]) + ')\n'
        peer_data += '... ' + str(len(self.peers_list) - 1) + ' more peers'
        tracker_table.rows.append(['Peers in swarm', peer_data])

        return str(tracker_table)

class torrent_tracker():

    def __init__(self, torrent):
        
        # connection status of the trackers
        self.connection_success         = 1 
        self.connection_failure         = 2
        self.connection_not_attempted   = 3

        # get all the trackers list of the torrent data
        self.trackers_list = []
        self.trackers_connection_status = []
        self.httpTrackers = []
        self.udpTrackers = []
        for tracker_url in torrent.torrent_metadata.trackers_urlList:
            #classify HTTP and UDP torrent trackers
            if 'http' in tracker_url[:4]:
                #here send it to the http tracker class and further estab conn.
                self.httpTrackers.append(tracker_url)
                tracker = http_torrent_tracker(torrent, tracker_url)
               # print(tracker)
            if 'udp' in tracker_url[:4]:
                #here send it to the udp tracker class and further estab conn.
                self.udpTrackers.append(tracker_url)
                tracker = udp_torrent_tracker(torrent, tracker_url)
            # append the tracker class instance 
            self.trackers_list.append(tracker)
            # append the connection status 
            self.trackers_connection_status.append(self.connection_not_attempted)


        print("-----HTTP tracker urls-----\n",self.httpTrackers)
        print("-----UDP tracker urls-----\n",self.udpTrackers)

    def request_connection(self):
    # attempts connecting with any of the tracker obtained in the list
        for i, tracker in enumerate(self.trackers_list):
            # check if you can request for torrent information 
            if(tracker.get_torrent_info()):
                self.trackers_connection_status[i] = self.connection_success
                self.client_tracker = tracker
                break
            else:
                self.trackers_connection_status[i] = self.connection_failure
        
        
        # returns tracker instance for which successful connection was established
        return self.client_tracker
         

class bittorrent_client():
    
    #Reads the torrent file and creates torrent class object
    def __init__(self, path):
        # get the torrent file path 
        torrent_file_path = path

        # read metadata from the torrent torrent file 
        self.torrent_info = torrent_file_reader(torrent_file_path)
        print(self.torrent_info)

        # decide whether the user want to download or seed the torrent
        self.client_request = { 'downloading': None, 'seeding': None}
        self.client_request['downloading'] = torrent_file_path                       
        # make torrent class instance from torrent data extracted from torrent file
        self.torrent = torrent(self.torrent_info.get_data(), self.client_request)
        print("Bittorrent Client-:")
        print(self.torrent)
        


    def contact_trackers(self):

        # get list of torrent tracker object from torrent file
        self.trackers_list = torrent_tracker(self.torrent)
        self.active_tracker = self.trackers_list.request_connection()
        print("Active trackers-:\n",self.active_tracker)

    """
        function initilizes swarm from the active tracker connection 
        response peer data participating in file sharing
    """
    def initialize_swarm(self):
        
        # get the peer data from the recieved from the tracker
        peers_data = self.active_tracker.get_peers_data()
            
        if self.client_request['downloading'] != None:

            # create swarm instance from the list of peers 
            self.swarm = swarm(peers_data, self.torrent)
        

    """
        function helps in downloading the torrent file form swarm 
        in which peers are sharing file data
    """
    def download(self):
        # download file initialization 
        download_file_path = self.client_request['downloading'] + self.torrent.torrent_metadata.fileName

        # create file handler for downloading data from peers
        file_handler = torrent_common_file_handler(download_file_path, self.torrent)

        # initialize file handler for downloading
        file_handler.initialize_for_download()
        
        # distribute file handler among all peers for reading/writing
        self.swarm.add_common_file_handler(file_handler)
        
        # lastly download the whole file
        self.swarm.file_Download() 

         
        
class torrent_statistics():
    # initialize all the torrent statics information
    def __init__(self, torrent_metadata):
        self.uploaded               = set([])   # pieces uploaded
        self.downloaded             = set([])   # pieces downloaded
       
        self.num_pieces_downloaded  = 0         # blocks/pieces downloaded
        self.num_pieces_uploaded    = 0         # blocks/pieces uplaoded
        self.num_pieces_left        = 0         # blocks/pieces left
        
        # file in bytes to be downloaded
        self.file_size              = torrent_metadata.fileSize
        # total pieces in file to be downloaded
        self.total_pieces           = int(len(torrent_metadata.pieces) / 20)


class torrent():

    def __init__(self, torrent_metadata, client_request):
        # store the orginal metadata extracted from the file
        self.torrent_metadata   = torrent_metadata
        self.client_request     = client_request
        self.client_port = 6883
        self.client_IP = ''
        # pieces divided into chunks of fixed block size #16KB
        self.block_length   = 16 * (2 ** 10) 
        
        # piece length of torrent file
        self.pieceLength = torrent_metadata.pieceLength

        # downloaded and uploaded values
        self.statistics = torrent_statistics(self.torrent_metadata)
        # the count of the number pieces that the files is made of
        self.pieces_count = int(len(self.torrent_metadata.pieces) / 20)

        # peer id encoded with azureus style encoding
        self.peer_id = ('-AZ2060-' + ''.join([str(rd.randint(0, 9)) for i in range(12)])).encode()
    
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
        # info hash
        torrent_file_table.rows.append(['Info hash', '20 Bytes file info hash value'])
        # files (multiple file torrents)
        if self.torrent_metadata.files:
            torrent_file_table.rows.append(['Files', str(len(self.torrent_metadata.files))])
        else:
            torrent_file_table.rows.append(['Files', str(self.torrent_metadata.files)])
        # number of pieces in file 
        torrent_file_table.rows.append(['Number of Pieces', str(self.pieces_count)])
        # client port
        torrent_file_table.rows.append(['Client port', str(self.client_port)])
        torrent_file_table.rows.append(['Client peer ID', str(self.peer_id)])
        
        return str(torrent_file_table)


path = sys.argv[1]
client = bittorrent_client(path)
client.contact_trackers()
client.initialize_swarm()
client.download()





