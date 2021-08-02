'''
Python parser example.
To use python parsers, first you must install JEP, see https://github.com/sepinf-inc/IPED/wiki/User-Manual#python-modules
Save your parser in 'parsers' folder. The class name must be equal to the script name without the extension. 
For more info about general parser api, see https://github.com/sepinf-inc/IPED/wiki/Contributing
'''

from org.apache.tika.sax import XHTMLContentHandler
from org.apache.tika.io import TikaInputStream
from org.apache.tika.io import TemporaryResources
from org.apache.tika.metadata import Metadata, Message
from org.apache.tika.exception import TikaException
from org.apache.tika.extractor import EmbeddedDocumentExtractor
from org.apache.tika.sax import EmbeddedContentHandler
from org.apache.tika.parser.html import HtmlParser
from iped3.util import ExtraProperties
from iped3.util import BasicProps
from dpf.sp.gpinf.indexer.parsers import IndexerDefaultParser
from dpf.sp.gpinf.indexer.util import EmptyInputStream
from dpf.mg.udi.gpinf.whatsappextractor import Util
from dpf.sp.gpinf.indexer.parsers.util import IndentityHtmlParser
from org.apache.commons.codec.binary import StringUtils
from java.io import ByteArrayInputStream
import os
import re
import sys
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from datetime import datetime, tzinfo

class PythonParserJabber:
    
    instant_message_mime = "message/x-jabber-message"

    '''
    Example of a python parser. This class must be thread safe.
    One way of achieving this is creating an immutable class i.e. do not create instance attributes.
    '''
    
    def getSupportedTypes(self, context):
        '''
        Returns:
            list of supported media types handled by this parser
        '''
        return ["application/x-jabber-chat"]

        # return ["application/xxxxxx"]


# def getSupportedTypesQueueOrder(self):
    '''
    This method is optional. You only need to implement it if your parser
    needs to access other case items different from the item being processed.
    E.G. you want to access case multimedia files while processing a chat database
    to insert the attachments in the chats being decoded. To work, you need to
    process the database mediaType after the attachments, in a later queue,
    so the attachments will be already indexed and ready to be searched for.
    Default queue number is 0 (first queue) if not defined for a mediaType.
        
        Returns:
            dictionary mapping mediaTypes to a queue number
        '''    
        # return {"application/xxxxxx" : 1}
    
    
    def parse(self, stream, handler, metadata, context):
        '''
         Parses each item found in case of the supported types.
         
         Parameters:
            stream: java.io.InputStreareadResourceAsStringm
                the raw (binary) content of the file
            handler: org.xml.sax.ContentHandler
                the content handler where you should output parsed content
            metadata: org.apache.tika.metadata.Metadata
                the metadata object from where you can get basic properties and store new parsed ones.
            context: org.apache.tika.parser.ParseContext
                the parsing context from where you can get parsing configuration
                
        Raises
            IOException: java.io.IOException
                if the file stream being read throws an IOException
            SAXException: org.xml.sax.SAXException
                if there is an error when writing the parser output to the handler.
            TikaException: org.apache.tika.exception.TikaException
                you can throw a TikaException if the file being parsed is corrupted or not supported.
        '''
        
        MSG_TEMPLATE = """
        <div class="linha" id="PYTHON_PARSER_MSG_ID">
        <div class="PYTHON_PARSER_DIRECTION">
        <span style="font-family: 'Roboto-Medium'; color: #b4c74b;">PYTHON_PARSER_SENDER</span><br/>
        PYTHON_PARSER_MSG<br/><span class="time">
        PYTHON_PARSER_DATE
        </span>
        </div></div>
        """

        xhtml = XHTMLContentHandler(handler, metadata);
        xhtml.startDocument()
        
        # uncomment if used below
        tmpResources = TemporaryResources()
        try:
            '''
            Read file contents from the stream using the java.io.InputStream API.
            Do not hold too much data in memory. If you neUtil.readResourceAsString("wachat-html-template.txt")ed, you can spool to file
            using the following code to create a temp file with the contents:
            
            from org.apache.tika.io import TikaInputStream
            tis = TikaInputStream.get(stream, tmpResources)
            tmpFilePath = tis.getFile().getAbsolutePath()
            '''

            extractor = context.get(EmbeddedDocumentExtractor)
            tis = TikaInputStream.get(stream, tmpResources)
            tmpFilePath = tis.getFile().getAbsolutePath()
            origFileName = metadata.get(Metadata.RESOURCE_NAME_KEY)
            
            # extract text from html chat to be indexed, searched for regexes and so on...
            HtmlParser().parse(tis, EmbeddedContentHandler(xhtml), metadata, context)

            soup = BeautifulSoup(open(tmpFilePath,'r'), "html.parser")
            body = soup.find("body")
            title =soup.find('title').text
            temp_to_date = title.split(" on ",1)[0]
            temp_client_app = title.split(" on ",1)[1].split()
            app = temp_client_app[1].strip("(").strip(")")
            client = temp_client_app[0].strip("/")
            host_system = "sistema_%s_%s"%(app,client)
            participants = [client, temp_to_date.split(" at ",1)[0].split("with ",1)[1]]
            # message_day = temp_to_date.split(" at ",1)[1].split(" ",1)[0]
            message_day = re.search("\d{2}/\d{2}/\d{4}",temp_to_date).group(0)
            filedate = os.path.basename(origFileName).replace(".html","").replace("BRT","")
            filedate_tz = datetime.strptime(filedate, '%Y-%m-%d.%f%z').tzinfo

            messages_list=[]
            all_lines = body.find_all('br')

            # There are at least two possible formats for the messages.
            # 1: <span style="color: #16569E"><span style="font-size: smaller">(18:02:46)</span> <b>msn.do.thor1@jabber.ru/7433774929690452792:</b></span> man acho q peguei algo aqui nesse js, q baixa la no pc<br>
            # 2: <font color="#A82F2F"><font size="2">(12:05:01)</font> <b>Coyote.:</b></font> <body>N viajei esse ano n</body><br/>
            # Find out which format
            possible_tags = ["span","font"]
            curr_tag = None

            # This code catches the rare exceptions for unkown tags, but increases the processing time.
            # Leaving the original code then

            # for tag in possible_tags:
            #     for i in range(0,len(all_lines)):
            #         test_syntax = all_lines[i].find_previous_sibling(tag)
            #         if test_syntax:
            #             curr_tag = tag
            #             break
            # if not curr_tag:
            #     print("STOP: %s"%all_lines)
                
            for tag in possible_tags:
                test_syntax = all_lines[0].find_previous_sibling(tag)
                if test_syntax:
                    curr_tag = tag



            html_messages = [x.find_previous_sibling(curr_tag) for x in all_lines]
            # Older versions (curr_tag = "font"), text messages with multiple <br> are not structured using html tags. Remove duplicated
            if curr_tag == "font":
                html_messages = list(set(html_messages))

            for idx, html_message in enumerate(html_messages):

                # Few messages with value None. Ignore them.
                if not html_message:
                    continue

                # If the format "dd/mm/aaaa" is not present, then this is a formatted message. 
                # In that case, date and nickname data are stored in the previous tag.
                if not html_message.find(text=re.compile("\d{2}:\d{2}:\d{2}")):
                    curr_content = html_message
                    curr_metadata = html_message.find_previous_sibling(curr_tag)
                else:

                    # If the date format is found, then there are two possibilities: a simple text message, or a system message.
                    # In the first case, there are 2 span tags, the first one comprising color and font, and the second one comprising date and nickname.
                    # curr_content = self.get_content_until_tag(html_message, curr_tag)
                    res = []
                    nextNode = html_message
                    while True:
                        nextNode = nextNode.nextSibling
                        try:
                            tag_name = nextNode.name
                        except AttributeError:
                            tag_name = ""

                        if nextNode and tag_name != curr_tag:
                            if isinstance(nextNode, NavigableString):
                                res.append(nextNode.string)
                            elif isinstance(nextNode, Tag):
                                res.append(nextNode.text)
                        else:
                            break
                    curr_content = " ".join([x for x in res if x not in [" ", "", "\n",None]])
                    curr_metadata = html_message

                        

                idict={}
                if curr_tag == "span":
                    if curr_metadata.find(curr_tag,style=True):                
                        # Skipping the suffix (it will capture  alice@jabber.br if the user is alice@jabber.br/7433774929690452792)
                        idict["message_sender"] = curr_metadata.find("b").text.rsplit("/",1)[0]

                    else:
                        idict["message_sender"] =  host_system
                elif curr_tag == "font":
                    if curr_metadata.find("b"):
                        idict["message_sender"] = curr_metadata.find("b").text.rsplit("/",1)[0]
                    else:
                        idict["message_sender"] =  host_system

                message_time = re.search("\d{2}:\d{2}:\d{2}",curr_metadata.text).group(0)
                dateobj = datetime.strptime("%sT%s"%(message_day,message_time),"%d/%m/%YT%H:%M:%S")
                idict["message_date"] = dateobj.replace(tzinfo = filedate_tz).isoformat()

                idict["message_text"] = curr_content
                messages_list.append(idict)



            # This validation is based in at least one username being a substring of the nickname, normally the client app in which the chat data was captured.
            #eg: username: alice@jabber.br nickname: alice@jabber.br/7433774929690452792
            # nicknames = list(set([x["message_sender"] for x in messages_list]))

            # participant_nickname_dict = {}
            # for curr_nick in nicknames:
            #     if client in curr_nick or curr_nick == host_system:
            #         participant_nickname_dict[curr_nick] = curr_nick
            #     # Normally there is only one nickame (eg bob2020) which is remote. The other ones follow the format alice@jabber.br/0123456789
            #     # Host_system is not a participant, it is create by the parser to be the sender from the system messages.
            #     else:
            #         participant_nickname_dict[curr_nick] = [x for x in participants if client not in x][-1]

            # # make sure there is a receiver in chat files comprising only one user and the host_system
            # if len(nicknames) == 1 or (len(nicknames) == 2 and host_system in nicknames):
            #     other_participant = [x for x in participants if x not in [y.split("/",1)[0] for y in participant_nickname_dict.values()]][-1]
            #     participant_nickname_dict[other_participant] = other_participant
            
            new_messages_list = []
            msg_num = 0
            msg_name_prefix = "Jabber chat message "
            sorted_msgs_list = sorted(messages_list, key=lambda k: k['message_date'])
            for m in sorted_msgs_list:
                iped_date = m["message_date"]
                iped_sender = m["message_sender"]
                if iped_sender == host_system:
                    iped_receiver = client
                else:
                    # remote participant sent the message
                    iped_receiver = [x for x in participants if x not in [iped_sender,host_system]][-1]

                iped_text = m["message_text"]
                if client in iped_sender:
                    iped_direction = "outgoing to"
                else:
                    iped_direction = "incoming from"

                meta = Metadata()
                meta.set(BasicProps.LENGTH, "")
                meta.set(Metadata.RESOURCE_NAME_KEY, msg_name_prefix + str(msg_num))
                meta.set(Message.MESSAGE_FROM, iped_sender)
                meta.set(Message.MESSAGE_TO, iped_receiver)
                meta.set(ExtraProperties.MESSAGE_DATE,iped_date)
                meta.set(ExtraProperties.MESSAGE_BODY,iped_text)
                meta.set(IndexerDefaultParser.INDEXER_CONTENT_TYPE, self.instant_message_mime)
                extractor.parseEmbedded(EmptyInputStream(), handler, meta, False)

                # xhtml.characters(" - ".join([iped_date, iped_sender, iped_text]))
                new_messages_list.append({"sender":iped_sender, "receiver":iped_receiver, "date":iped_date, "msg":iped_text, "direction":iped_direction})
                
                msg_num += 1

            # Code below generates html in whatsapp format. For now we are giving
            # preference to original jabber html, so this is commented out.
            ''' 
            formatted_msgs = []
            for res in new_messages_list:
                if not isinstance(res["msg"], str):
                    res["msg"] = res["msg"].text
                msg_template = MSG_TEMPLATE
                formatted_msg = msg_template.replace("PYTHON_PARSER_SENDER", res["sender"])\
                                                .replace("PYTHON_PARSER_MSG_ID", "0")\
                                                .replace("PYTHON_PARSER_MSG", res["msg"])\
                                                .replace("PYTHON_PARSER_DATE", res["date"])\
                                                .replace("PYTHON_PARSER_DIRECTION", res["direction"])
                                                                                            
                formatted_msgs.append(formatted_msg)


            formatted_text = "\n".join(formatted_msgs)
            util = Util()
            html_chat_template = util.readResourceAsString("wachat-html-template.txt")
            css_template = util.readResourceAsString("css/whatsapp.css") 
            js_template = util.readResourceAsString("js/whatsapp.js")
            avatar = util.getImageResourceAsEmbedded("img/avatar.png")
            favicon = util.getImageResourceAsEmbedded("img/favicon.ico")


            final_html = html_chat_template.replace("${messages}", formatted_text).replace("${title}",title)\
                            .replace("${css}",css_template).replace("${javascript}",js_template)\
                            .replace("${favicon}",favicon).replace("${avatar}",avatar)\
                            .replace("${id}",os.path.split(tmpFilePath)[1])
            
            byteInputStream = ByteArrayInputStream(StringUtils.getBytesUtf8(final_html))
            IndentityHtmlParser().parse(byteInputStream, context, xhtml)
            '''

        except Exception as exc:
            raise exc


        finally:

            xhtml.endDocument()
#            if tmpResources is used above you must close itEmbeddedDocumentExtractor.class
            tmpResources.close()
                   