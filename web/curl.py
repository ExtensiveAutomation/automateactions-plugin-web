
import sys
import subprocess
import time
import uuid
import os
import tempfile

n = os.path.normpath
file_path = os.path.dirname(os.path.abspath(__file__))
plugin_path = os.sep.join(file_path.split(os.sep)[:-1])


if sys.platform == 'win32':
    CURL_BIN = "curl"
else:
    CURL_BIN = "%s/bin/curl.exe" % plugin_path
CURL_BIN = n(CURL_BIN)

class Curl():
    def __init__(self, action, debug=False):
        """init class"""
        self.action = action
        self.debug = debug
        
    def trace_send(self, message):
        """"trace message"""
        if self.debug:
            self.log_send(message=message)
            
    def trace_recv(self, message):
        """"trace message"""
        if self.debug:
            self.log_recv(message=message)

    def log_send(self, message):
        """send message"""
        self.action.log(message="> %s" % message)
        
    def log_recv(self, message):
        """received message"""
        self.action.log(message="< %s" % message)
       
    def sendHttp(self, host, method=None, headers=None, body=None, more=None, 
                       proxy_host=None, timeout_connect=10, timeout_max=10):
        """send http request"""
        infile = "%s/req_%s" % (tempfile.gettempdir(), uuid.uuid4())
        infile = n(infile)
        
        outfile = "%s/rsp_%s" % (tempfile.gettempdir(), uuid.uuid4())
        outfile = n(outfile)
        
        curl_cmd = '%s -v -s ' % (CURL_BIN)
        curl_cmd += ' --user-agent AutomateActions'

        if method is not None:
            curl_cmd += " -X %s" % method
        if headers is not None:
            for hdr in headers.splitlines():
                curl_cmd += ' -H "%s"' % hdr
        if proxy_host is not None:
            curl_cmd += ' -x %s' % proxy_host

        if more is not None:
            curl_cmd += " %s" % (more)
            
        curl_cmd += ' -w '
        curl_cmd += '"\\n%{time_connect};%{time_total};%{speed_download};'
        curl_cmd += '%{time_appconnect}; %{time_namelookup};'
        curl_cmd += '%{http_code};%{size_download};'
        curl_cmd += '%{url_effective};%{remote_ip}\\n"'

        curl_cmd+= '	--connect-timeout %s --max-time %s ' % ( int(timeout_connect), 
                                                                 int(timeout_max) )
        curl_cmd += ' -o "%s"' % outfile
        
        if body is not None:
            with open(infile, "wb") as f:
                f.write( bytes(body, 'utf8')  )
            curl_cmd += ' --data-binary "@%s"'  % infile

        curl_cmd += ' 	%s' % host
        
        self.trace_send(curl_cmd)
        
        ps = subprocess.Popen(curl_cmd, shell=True, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.STDOUT,
                              bufsize=0)
        
        conn_info = []
        req_out = []
        rsp_in = []
        
        conn_dict = {}
        req_dict = {}
        rsp_dict = {}
        
        while True:
            line = ps.stdout.readline()
            
            if sys.platform == 'win32':
                console_encoding = 'cp850'
            else:
                console_encoding = 'utf-8'
            line = line.decode(console_encoding)

            if line != '':
                time.sleep(0.01)
                
                if line.startswith("*"):
                    conn_info.append(line[1:].strip())
                    
                elif line.startswith("> "):
                    req_out.append(line[2:].strip())
                    
                elif line.startswith("< "):
                    if not len(rsp_in):
                    
                        # extract http version, method and uri
                        req_head = req_out[0].split(" ", 2)
                        req_dict["method"] = req_head[0]
                        req_dict["uri"] = req_head[1]
                        req_dict["version"] = req_head[2]
                        req_dict["headers"] = req_out[1:]
                        
                        req_dict["body"] = ""
                        if body is not None:
                            req_dict["body"] = body
                            
                        self.log_send(message=req_out[0])
                        for l in req_out[1:]:
                            self.trace_send(message=l)
                            
                    rsp_in.append(line[2:].strip())	
                    
                elif line.startswith("{"):
                    continue
                    
                elif line.startswith("}"):
                    continue
                    
                else:
                    conn_info.append(line.strip())
            else:
                break
                
        rsp_body=None
        if len(rsp_in):
        
            # extract http version, code and phrase
            rsp_head = rsp_in[0].split(" ", 2)
            rsp_dict["code"] = rsp_head[1]
            rsp_dict["version"] = rsp_head[0]
            if len(rsp_head) > 2:
                rsp_dict["phrase"] = rsp_head[2]
            else:
                rsp_dict["phrase"] = ""
                
            rsp_dict["headers"] = rsp_in[1:]

            # search body encoding from content-type header
            encoding_body = "utf8"
            for h in rsp_dict["headers"]:
                # todo regex will be better
                if "Content-Type" in h:
                    if "charset=" in h:
                        encoding_body = h.split("charset=")[1].split(";")[0]
                
            # read body from file
            rsp_dict["body"] = ""
            with open(outfile, encoding=encoding_body) as f:
                rsp_body = f.read() 
                rsp_dict["body"] = rsp_body

            # log response
            self.log_recv(message=rsp_in[0])
            for l in rsp_in[1:]:
                self.trace_recv(message=l)
                            
        conn_stats = conn_info[-1].split(";")
        conn_dict["statistics"] = {}
        conn_dict["statistics"]["time-connect"] = conn_stats[0]
        conn_dict["statistics"]["time-total"] = conn_stats[1]
        conn_dict["statistics"]["speed-download"] = conn_stats[2]
        conn_dict["statistics"]["time-appconnect"] = conn_stats[3]
        conn_dict["statistics"]["time-namelookup"] = conn_stats[4]
        conn_dict["statistics"]["http-code"] = conn_stats[5]
        conn_dict["statistics"]["size-download"] = conn_stats[6]
        conn_dict["statistics"]["url-effective"] = conn_stats[7]
        conn_dict["statistics"]["remote-ip"] = conn_stats[8]
        
        conn_dict["debug"] = conn_info[:-1]
        try:
            os.remove(infile)
            os.remove(outfile)
        except:
            pass
            
        return (conn_dict, req_dict, rsp_dict)