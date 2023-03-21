from  connect_tracker import *
import argparse


def initiate(user_arg):
    client = bittorrent_client(user_arg)
    client.contact_trackers()
    client.initialize_swarm()
    client.download()
    


bittorrent_description = "+++++++++++-------------------------My BitTorrent Client-------------------------+++++++++++"
parser = argparse.ArgumentParser(description=bittorrent_description)
parser.add_argument(TORRENT_FILE_PATH, help='file path of torrent file') 
parser.add_argument("-d", "--" + DOWNLOAD_DIR_PATH, help="directory path of downloading file")
parser.add_argument("-m", "--" + MAX_PEERS, help="maximum peers participating in download of file")


# get the user input option after parsing the command line argument
options = vars(parser.parse_args(sys.argv[1:]))
if(options[DOWNLOAD_DIR_PATH] is None):
    print('Bittorrent works with download argument, try using --help')
    sys.exit()
    
initiate(options)

