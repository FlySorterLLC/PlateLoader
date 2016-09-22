
import wx

class MyFrame(wx.Frame):
    """ We simply derive a new class of Frame. """
    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title, size=(800,480))
        self.SetBackgroundColour(wx.WHITE)
        bmpArray = []
        box = wx.BoxSizer(wx.VERTICAL)
        for i in range(8):
            hBox = wx.BoxSizer(wx.HORIZONTAL)
            for j in range(12):
                b = wx.StaticBitmap(self, bitmap=wx.EmptyBitmap(15, 15))
                t = wx.StaticText(self, size=wx.Size(25, -1),
                                  label="{0}{1}".format(chr(i+ord('A')), j+1),
                                  style=wx.ALIGN_RIGHT)
                hBox.Add(t, 0, wx.ALL, 5)
                hBox.Add(b, 0, wx.ALL, 5)
                bmpArray.append(b)
            box.Add(hBox, 0, wx.ALL, 5)
        hBox = wx.BoxSizer(wx.HORIZONTAL)
        self.startButton = wx.Button(self, label="Start")
        self.resetButton = wx.Button(self, label="Reset")
        hBox.Add(self.startButton, 0, wx.ALL, 5)
        hBox.Add(self.resetButton, 0, wx.ALL, 5)
        box.Add(hBox, 0, wx.CENTER, 5)
        self.SetSizer(box)
        self.Layout()
        self.Show(True)

app = wx.App(False)
frame = MyFrame(None, 'FlySorter Plate Loader')
app.MainLoop()
