'''
AFNI NIML dataset I/O support.
Usually this type of datasets are used for functional data (timeseries, 
preprocessed data), statistical maps or searchlight results. 

Created on Feb 19, 2012

@author: nick
'''

import afni_niml, random, numpy as np, afni_niml_types as types, os, time, sys, afni_niml as niml

def _string2list(s,SEP=";"):
    '''splits a string by SEP; if the last element is empty then it is not returned
    
    The rationale is that AFNI/NIML like to close the string with a ';' which 
    would return one (empty) value too many'''
    r=s.split(SEP)
    if not r[-1]:
        r=r[:-1]
    return r

def rawniml2dset(p):
    if type(p) is list:
        return map(rawniml2dset,p)
    
    assert type(p) is dict and all([f in p for f in ['dset_type','nodes']]), p
    
    r=dict()
    r['dset_type']=p['dset_type']
    
    for node in p['nodes']:
        assert 'name' in node
        
        name=node['name']
        data=node.get('data',None)
        
        if name=='INDEX_LIST':
            r['node_indices']=data
        elif name=='SPARSE_DATA':
            r['data']=data
        elif name=='AFNI_atr':
            atr=node['atr_name']
            
            if atr=='HISTORY_NOTE':
                r['history']=data
            elif atr=='COLMS_STATSYM':
                r['stats']=_string2list(data)
            elif atr=='COLMS_LABS':
                r['labels']=_string2list(data)
        else:
            continue; #raise ValueError("Unexpected node %s" % name)
        
    return r
    

def _dset2rawniml_header(s):
    r=dict()
    
    # set dataset type, default is Node_Bucket
    r['dset_type']=s.get('dset_type','Node_Bucket')
    
    # make a new id code of 24 characters, all uppercase letters
    r['self_idcode']=niml.getnewidcode()
    r['filename']=s.get('filename','null')
    r['label']=r['filename']
    r['name']='AFNI_dataset'
    r['ni_form']='ni_group'
    
    return r
    
def _dset2rawniml_data(s):
    return dict(data_type='Node_Bucket_data',
                name='SPARSE_DATA',
                data=s['data'])
    
def _dset2rawniml_nodeidxs(s):
    nrows=s['data'].shape[0]
    
    node_idxs=s.get('node_indices') if 'node_indices' in s else np.arange(nrows,dtype=np.int32)
    if not type(node_idxs) is np.ndarray:
        node_idxs=np.asarray(node_idxs,dtype=np.int32)
    
    if node_idxs.size!=nrows:
        raise ValueError("Size mismatch for node indices (%r) and data (%r)" % 
                         (node_idxs.size,nrows))
    
    if node_idxs.shape!=(nrows,1):
        node_idxs=np.reshape(node_idxs,((nrows,1))) # reshape to column vector if necessary
        
    def is_sorted(v): # O(1) in best case and O(n) in worst case (unlike sorted())
        n=len(v)
        return n==0 or all(v[i]<=v[i+1] for i in xrange(n-1))
    
    return dict(data_type='Node_Bucket_node_indices',
                name='INDEX_LIST',
                data=node_idxs,
                sorted_node_def='Yes' if is_sorted(node_idxs) else 'No')
    
def _dset2rawniml_datarange(s):
    data=s['data']
    
    minpos=np.argmin(data,axis=0)
    maxpos=np.argmax(data,axis=0)
    
    f=types.numpy_data2printer(data) # formatter function
    r=[]
    for i in xrange(len(minpos)):
        mnpos=minpos[i]
        mxpos=maxpos[i]
        r.append('%s %s %d %d' % (f(data[mnpos,i]),f(data[mxpos,i]),mnpos,mxpos))

    # range of data in each column
    return dict(atr_name='COLMS_RANGE',
                data=r)
    
def _dset2rawniml_labels(s):
    ncols=s['data'].shape[1]
    labels=list(s.get('labels',None) or ('col_%d' % i for i in xrange(ncols)))
    if len(labels)!=ncols:
        raise ValueError("Wrong number of labels: found %d but expected %d" % 
                         (len(labels,ncols)))
    return dict(atr_name='COLMS_LABS',
                data=labels)

def _dset2rawniml_history(s):
    logprefix=('[%s@%s: %s]' % (os.environ['USER'],
                                os.uname()[1],
                                time.asctime()))
    # history
    history=s.get('history', '')
    if history and history[-1]!='\n':
        history+=('\n')
    history+='%s Saved by %s:%s' % (logprefix,
                                    __file__,
                                    sys._getframe().f_code.co_name)
    history=str(history.decode('utf-8'))
    return dict(atr_name='HISTORY_NOTE',
                data=history)

def _dset2rawniml_datatypes(s):
    data=s['data']
    ncols=data.shape[1]
    datatype=['Generic_Int' if types.numpy_data_isint(data) else 'Generic_Float']*ncols
    return dict(atr_name='COLMS_TYPE',
                data=datatype)

def _dset2rawniml_stats(s):
    data=s['data']
    ncols=data.shape[1]
    stats=s.get('stats',None) or ['none']*ncols
    return dict(atr_name='COLMS_STATSYM',
                data=stats)

def _dset2rawniml_complete(r):
    '''adds any missing information and ensures data is formatted properly'''
    
    # if data is a list of strings, join it and store it as a string
    # otherwise leave data untouched
    while True:
        data=r['data']
        tp=type(data)
    
        if tp is list:
            if not data or type(data[0]) is str:
                r['data']=";".join(data)
                # new data and tp values are set in next (and final) iteration
            else:
                raise TypeError("Illegal type %r" % tp)
        else:
            break # we're done
    
    if tp is str:
        r['ni_dimen']='1'
        r['ni_type']='String'
    elif tp is np.ndarray:
        data=types.nimldataassupporteddtype(data)
        r['data']=data # ensure we store a supported type
        
        nrows,ncols=data.shape
        r['ni_dimen']=str(nrows)
        tpstr=types.numpy_type2name(data.dtype)
        r['ni_type']='%d*%s' % (ncols,tpstr) if nrows>1 else tpstr
    else:
        raise TypeError('Illegal type %r' % tp)
    
    if not 'name' in r:
        r['name']='AFNI_atr'
    
    return r
    

def dset2rawniml(s):
    if type(s) is list:
        return map(dset2rawniml,s)
    elif type(s) is np.ndarray:
        s=dict(data=s)
    
    if not 'data' in s:
        raise ValueError('No data?')
    
    r=_dset2rawniml_header(s)
    builders=[_dset2rawniml_data,
              _dset2rawniml_nodeidxs,
              _dset2rawniml_labels,
              _dset2rawniml_datarange,
              _dset2rawniml_history,
              _dset2rawniml_datatypes,
              _dset2rawniml_stats]
    
    nodes=[_dset2rawniml_complete(build(s)) for build in builders]
    r['nodes']=nodes    
    return r

def read(fn,itemifsingletonlist=True):
    return niml.read(fn, itemifsingletonlist, rawniml2dset)

def write(fnout,dset,form='binary'):
    fn=os.path.split(fnout)[1]
    dset['filename']=fn
    niml.write(fnout, dset, form, dset2rawniml)

def _test_dset():
    d='/Users/nick/Downloads/fingerdata-0.2/glm/'
    fn=d+'__small.niml.dset'
    #fn=d+'lh_voxsel_50vx.niml.dset'
    fn=d+'lh_cfy_50vx.niml.dset'
    #fn=d+'__binary.niml.dset'
    fn=d+'__big_binary.niml.dset'
    fn=d+'__b64.niml.dset'
    
    
    
    fnout=d+"__output.niml.dset"
    
    niml=read(fn)
    
    write(fnout,niml)
    
    '''
    f=open(fn)
    s=f.read()
    f.close()
    
    raw=niml.string2rawniml(s)
    simple=rawniml2dset(raw)
    shortfn=os.path.split(fn)[1]
    simple[0]['filename']=shortfn
    raw2=dset2rawniml(simple)
    s2=niml.rawniml2string(raw2,form='binary')
    
    f=open(fnout,'w')
    f.write(s2)
    f.close()
    '''
    print fnout
    
if __name__=='__main__':
    _test_dset()