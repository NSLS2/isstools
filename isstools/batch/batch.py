import pandas as pd
import collections
import numpy as np
from PyQt5 import QtGui

class BatchManager():

    def __init__(self, gui):
        self.gui = gui

    def load_csv(self, filepath):
        df = pd.read_csv(filepath, header=None, names=range(20))
        table_names = ['Create Samples', 'Create Scans', 'Create Sample Loops', 'Batch Mode']
        groups = df[0].isin(table_names).cumsum()
        tables = {g.iloc[0,0]: g.iloc[1:] for k,g in df.groupby(groups)}
        
        for name, columns in [[name, tables[name].columns[-1::-1]] for name in [table for table in tables.keys()]]:
            for column in columns:
                if tables[name][[column]].isnull().values.all():
                    tables[name] = tables[name].drop(tables[name].columns[[column]], axis = 1)
        
        for name in tables.keys():
            if not tables[name].empty:
                tables[name] = tables[name].reset_index(drop=True)
                tables[name] = tables[name].rename(columns=tables[name].iloc[0])
                tables[name] = tables[name].reindex(tables[name].index.drop(0))
                tables[name] = tables[name].reset_index(drop=True)
        
        for name, columns in [[name, tables[name].columns[-1::-1]] for name in [table for table in ['Create Scans']]]:
            for column in columns:
                if tables[name][[column]].isnull().values.all():
                    tables[name] = tables[name].drop(tables[name].columns[[tables['Create Scans'].columns.get_loc(column)]], axis = 1)
        
        for name in tables.keys():
            for index, row in list(tables[name].iterrows())[-1::-1]:
                if row.isnull().values.all():
                    tables[name] = tables[name].drop(tables[name].index[[index]])
        
        self.gui.treeView_samples.model().clear()
        self.gui.treeView_scans.model().clear()
        self.gui.treeView_samples_loop.model().clear()
        self.gui.treeView_samples_loop_scans.model().clear()
        self.gui.treeView_batch.model().clear()

        if not tables['Create Samples'].empty:
            for index, row in tables['Create Samples'].iterrows():
                #print('{d[0]} X:{d[1]} Y:{d[2]}'.format(d=row.values))
                parent = self.gui.model_samples.invisibleRootItem()
                item = QtGui.QStandardItem('{d[0]} X:{d[1]} Y:{d[2]}'.format(d=row.values))
                item.x = float(row.values[1])
                item.y = float(row.values[2])
                parent.appendRow(item)
        
        def isNan(num):
            return num != num
        
        if not tables['Create Scans'].empty:
            for index, row in tables['Create Scans'].iterrows():
                #print('{d[0]} X:{d[1]} Y:{d[2]}'.format(d=row.values))
                parent = self.gui.model_scans.invisibleRootItem()
                text = ''
                for index_col, column in enumerate(tables['Create Scans'].columns):
                    if not isNan(tables['Create Scans'][column].iloc[index]):
                        text += '{d[' + str(index_col) + ']} '
                text = text[:-1]
                item = QtGui.QStandardItem(text.format(d=row.values))
                parent.appendRow(item)
        
        if not tables['Create Sample Loops'].empty:
            for index, row in tables['Create Sample Loops'].iterrows():
                parent_samples = self.gui.model_samples_loop.invisibleRootItem()
                parent_scans = self.gui.model_samples_loop_scans.invisibleRootItem()
                if not isNan(row.values[0]):
                    item_sample = QtGui.QStandardItem('{}'.format(row.values[0]))
                    parent_samples.appendRow(item_sample)
                if not isNan(row.values[1]):
                    item_scans = QtGui.QStandardItem('{}'.format(row.values[1]))
                    parent_scans.appendRow(item_scans)
        
        
        if not tables['Batch Mode'].empty:
            last_tree_parents = [[] for i in range(int(tables['Batch Mode']['Tree Level'].max()) + 1)]
            parent = self.gui.model_batch.invisibleRootItem()
            for index, row in tables['Batch Mode'].iterrows():
                item = QtGui.QStandardItem(row.values[0])
                if int(row.values[1]) == 0:
                    parent.appendRow(item)
                else:
                    last_tree_parents[int(row.values[1]) - 1].appendRow(item)
                    
                last_tree_parents[int(row.values[1])] = item

    def save_csv(self, filepath):
        # Samples
        model = self.gui.treeView_samples.model()
        data_samples = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            data_samples.append(str(model.data(index)))
        
        dic1 = collections.OrderedDict({'Name':[]})
        values = []
        for text in data_samples:
            dic1['Name'].append(text[:text.find(' X:')])
            values.append(collections.OrderedDict((k.strip(), v.strip()) for k, v in (item.split(':') for item in text[text.find(' X:') + 1:].split(' '))))
        
        dic2 = collections.OrderedDict()
        for key in values[0].keys():
            dic2[key] = []
        for index, value in enumerate(values):
            for index_val, key in enumerate(values[0].keys()):
                #print(key, values[index][key])
                dic2[key].append(values[index][key])
        
        samp_dic = dict(collections.OrderedDict({**dic1, **dic2}))
        csamp = pd.DataFrame().from_dict(samp_dic)
        
        
        # Scans
        model = self.gui.treeView_scans.model()
        data_scans = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            data_scans.append(str(model.data(index)))
        
        dic_aux = collections.OrderedDict({'Name':[]})
        values = []
        for text in data_scans:
            dic_aux['Name'].append(text[:text.rfind(' ', 0, text.find(':'))])
            values.append(collections.OrderedDict((k.strip(), v.strip()) for k, v in (item.split(':') for item in text[text.rfind(' ', 0, text.find(':')) + 1:].split(' '))))
        
        keys = list({item for sublist in [list(value.keys()) for value in values] for item in sublist})
        dic_scans = collections.OrderedDict()
        for index, value in enumerate(values):
            for key in values[index].keys():
                dic_scans[key] = []
        for index, value in enumerate(values):
            for index_key, key in enumerate(keys):
                if key in value:
                    dic_scans[key].append('{}:{}'.format(key, values[index][key]))
                else:
                    dic_scans[key].append(float('NaN'))
        
        dic_scans = dict(collections.OrderedDict({**dic_aux, **dic_scans}))
        #print(dic_scans)
        cscans = pd.DataFrame().from_dict(dic_scans)
        
        
        
        # Sample loop samples
        model = self.gui.treeView_samples_loop.model()
        data_sample_loop = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            data_sample_loop.append(str(model.data(index)))
        model = self.gui.treeView_samples_loop_scans.model()
        data_sample_loop_scans = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            data_sample_loop_scans.append(str(model.data(index)))
        
        dic_sample_loop = collections.OrderedDict({'Samples':[], 'Scans':[]})
        values = []
        for index in range(max([len(data_sample_loop), len(data_sample_loop_scans)])):
            if len(data_sample_loop) > index:
                dic_sample_loop['Samples'].append(data_sample_loop[index])
            else:
                dic_sample_loop['Samples'].append(float('NaN'))
            if len(data_sample_loop_scans) > index:
                dic_sample_loop['Scans'].append(data_sample_loop_scans[index])
            else:
                dic_sample_loop['Scans'].append(float('NaN'))
        
        csloop = pd.DataFrame().from_dict(dic_sample_loop)
        
        
        # Batch mode
        model = self.gui.treeView_batch.model()
        data_batch = []
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            item = index.model().itemFromIndex(index)
        
            data_batch.append([str(model.data(index)), 0])
            #print(item.rowCount())
            for child_index2 in range(item.rowCount()):
                item2 = item.child(child_index2)
                #print(item.child(child_index2).rowCount())
                data_batch.append([item2.text(), 1])
                for child_index3 in range(item2.rowCount()):
                    item3 = item2.child(child_index3)
                    data_batch.append([item3.text(), 2])
                    for child_index4 in range(item3.rowCount()):
                        item4 = item3.child(child_index4)
                        data_batch.append([item4.text(), 3])
                        for child_index5 in range(item4.rowCount()):
                            item5 = item4.child(child_index5)
                            data_batch.append([item5.text(), 4])
        dic_batch = collections.OrderedDict()
        dic_batch['Text'] = list(np.array(data_batch)[:, 0])
        dic_batch['Tree Level'] = list(np.array(data_batch)[:, 1])
        #dic_batch = collections.OrderedDict({'Text':list(np.array(data_batch)[:, 0]), 'Tree Level':list(np.array(data_batch)[:, 1])})
        batch = pd.DataFrame().from_dict(dic_batch)
        
        
        tables = dict({'Create Samples':csamp, 'Create Scans':cscans, 'Create Sample Loops':csloop, 'Batch Mode':batch})
        
        
        filename = filepath
        f = open(filename, 'w')
        f.write('Create Samples\n')
        f.close()
        
        f = open(filename, 'a')
        tables['Create Samples'].to_csv(f, index=False)
        
        f.write('\nCreate Scans\n')
        tables['Create Scans'].to_csv(f, index=False)
        
        f.write('\nCreate Sample Loops\n')
        tables['Create Sample Loops'].to_csv(f, index=False)
        
        f.write('\nBatch Mode\n')
        tables['Batch Mode'].to_csv(f, index=False)
        
        f.close() 
