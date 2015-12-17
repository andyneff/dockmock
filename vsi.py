#Shamelessly copied from https://bitbucket.org/visionsystemsinc/vsi_common/src/54918f249f9d82a04267fae4cc503bdc1c75ff51/python/vsi/tools/redirect.py
import os
import threading

class LoggerFile(object):
  def __init__(self, logger_command):
    self.logger_command=logger_command
  
  def write(self, str):
    str = str.rstrip()
    if str:
      self.logger_command(str)

class FileRedirect(object):
  def __init__(self, outputs=[]):
    self.outputs = outputs

  def __enter__(self):
    self.rids = []
    self.wids = []
    self.tids = [];
    
    for index, output in enumerate(self.outputs):
      r, w = os.pipe()
      self.rids.append(os.fdopen(r, 'rb'))
      self.wids.append(os.fdopen(w, 'wb'))
      
      self.startMonitor(index)
    
    return self
  
  def __exit__(self, exc_type=None, exc_value=None, traceback=None):
    for wid in self.wids:
      wid.close()
      
    for tid in self.tids:
      tid.join()

  def __bleed(self, streamIndex):
    rid = self.rids[streamIndex]
    wid = self.wids[streamIndex]
    output = self.outputs[streamIndex]

    #do-while
    chunk = True
    while chunk: #while rid isn't closed
      chunk = rid.readline(64*1024) #read a chunk
      output.write(chunk) #write chunk
    rid.close()

  def startMonitor(self, stream_index):
    self.tids.append(threading.Thread(target=self.__bleed, args=(stream_index,)))
    self.tids[-1].start()

class PopenRedirect(FileRedirect):
  def __init__(self, stdout=type('Foo', (object,), {'write':lambda x,y:None})(),
                     stderr=type('Bar', (object,), {'write':lambda x,y:None})()):
    self.stdout_output = stdout
    self.stderr_output = stderr
    
    super(PopenRedirect, self).__init__([stdout, stderr])

  @property
  def stdout(self):
    return self.wids[0]

  @property
  def stderr(self):
    return self.wids[1]
