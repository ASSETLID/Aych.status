#!/usr/bin/python

import yaml
try :
    from yaml import CBaseLoader as yamlLoader
except ImportError:
    from yaml import BaseLoader as yamlLoader
    warning('YAML C-library not available, falling back to python')

try :
    import cPickle as pickle
except ImportError:
    import pickle
    warning('Pickle C-library not available, falling back to python')

import fnmatch
import os
import argparse
import csv
import datetime as dt
import matplotlib.pyplot as plt
from matplotlib import dates
import os.path
from itertools import groupby
from operator import itemgetter, attrgetter, methodcaller
import collections
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

def parse(f):
    data = yaml.load(f, Loader=yamlLoader)
    d = {}
    if 'broken-packages' in data : 
        data = { x.replace('-', '_'): data[x] for x in data.keys() }
        d['broken_packages'] = data['broken_packages']
        d['total_packages'] = data['total_packages']
        d['ocaml_switch'] = data['ocaml_switch']
        d['date'] = data['date']
        d['commit'] = data['commit']
        d['report'] = {}
        for name, group in groupby(data['report'], lambda x: x['package']):
            for p in group:
                #print "%s => %s." % (name, p)
                if name in d['report'] :
                    d['report'][name].append(p)
                else :
                    d['report'][name] = [p]
    return d

#    { pippo : [ { 1.1 : { 4.01 : ok, 4.02 : broken } }, { 1.2 : { 4.01 : ok, 4.02 : broken } }, ] }
def aggregate(d):
    aggregatereport = {}
    summary = {}
    date = None
    commit = None
    for report in d :
        if report :
            date = report['date']
            commit = report['commit']
            switch = report['ocaml_switch']
            for name, l in report['report'].iteritems() :
                if name not in aggregatereport :
                    aggregatereport[name] = {}
                    summary[name] = {}

                status = {'ok' : 0, 'broken' : 0}
                for s,group in groupby(l, lambda p: p['status']) :
                    status[s] = len(list(group))

                if status['ok'] == len(l) :
                    summary[name][switch] = "ok"
                elif status['broken'] == len(l) :
                    summary[name][switch] = "broken"
                else :
                    summary[name][switch] = "partial"

                for package in l :
                    ver = package['version']
                    r = package['reasons'] if package['status'] == "broken" else ""
                    direct = False
                    indirect = False
                    dc,dm = [],[]
                    idc,idm = {}, {}
                    if 'reasons' in package :
                        for p in package['reasons'] :
                            if 'missing' in p :
                                pkgname = p['missing']['pkg']['package']
                                pkgvers = p['missing']['pkg']['version']
                                unsatdep = p['missing']['pkg']['unsat-dependency']
                                if pkgname == name :
                                    direct = True
                                    dm.append(unsatdep)
                                else :
                                    indirect = True
                                    if pkgname not in idm :
                                        idm[pkgname] = [pkgvers]
                                    else :
                                        idm[pkgname].append(pkgvers)

                            if 'conflict' in p :
                                if p['conflict']['pkg1']['package'] == name or p['conflict']['pkg2']['package'] == name :
                                    direct = True
                                else :
                                    indirect = True
                                p1 = p['conflict']['pkg1']['package']
                                p2 = p['conflict']['pkg2']['package']
                                v1 = p['conflict']['pkg1']['version']
                                v2 = p['conflict']['pkg2']['version']
                                dc.append(((p1,v1),(p2,v2)))

                    if ver in aggregatereport[name] :
                        aggregatereport[name][ver][switch] = (package['status'],(direct,indirect),dc,dm,idc,idm,r)
                    else :
                        s = {switch:(package['status'],(direct,indirect),dc,dm,idc,idm,r)}
                        aggregatereport[name][ver] = s

    summaryreport = {}
    summaryreport['totalnames'] = len(aggregatereport)
    summaryreport['broken'] = 0
    summaryreport['partial'] = 0
    summaryreport['correct'] = 0
    summaryreport['report'] = summary
    summaryreport['date'] = date
    summaryreport['commit'] = commit

    switchnumber = len(d)
    for name,switches in summary.iteritems() :
        ok,bad,partial = [], [], []
        print switches.values()
        for x in switches.values() :
            if x == "ok" :
                ok.append(x) 
            elif x == "bad" :
                bad.append(x)
            else :
                partial.append(x)
        if len(ok) == switchnumber and len(bad) == 0 and len(partial) == 0 :
            summaryreport['correct'] += 1
            summaryreport['report'][name]['status'] = "ok"
        elif len(ok) == 0 and len(bad) == switchnumber and len(partial) == 0 :
            summaryreport['broken'] += 1
            summaryreport['report'][name]['status'] = "broken"
        else :
            summaryreport['partial'] += 1
            summaryreport['report'][name]['status'] = "partial"

    return aggregatereport,summaryreport

# total number of package names on all Switch
# total number of packages for each Switch

# a package is Broken if it is broken for All (declared) Switch
# a package is Partially Broken if it is broken on Some (declared) Switch
# a package is Correct if it is installable on All (declared) Switch

def html_package(aggregatereport,switches,date):
    j2_env = Environment(loader=FileSystemLoader(THIS_DIR),trim_blocks=True)
    for name,versions in aggregatereport.iteritems() :
        template = j2_env.get_template('templates/package.html')
        output = template.render({'name' : name, 'versions' : versions, 'switches': switches, 'date' : date})
        dirname = os.path.join("html",str(date),'packages')
        if not os.path.exists(dirname) :
            os.makedirs(dirname)
        fname = os.path.join(dirname,name+".html")
        with open(fname, 'w') as f:
            f.write(output)

def html_summary(aggregatereport,summaryreport,switches):
    j2_env = Environment(loader=FileSystemLoader(THIS_DIR),trim_blocks=True)
    template = j2_env.get_template('templates/summary.html')
    output = template.render({'report' : aggregatereport, 'summary' : summaryreport, 'switches': switches})
    dirname = os.path.join("html",str(summaryreport['date']))
    if not os.path.exists(dirname) :
        os.makedirs(dirname)
    fname = os.path.join(dirname,"summary.html")
    with open(fname, 'w') as f:
        f.write(output)
 
def main():
    parser = argparse.ArgumentParser(description='create ows static pages')
    parser.add_argument('-v', '--verbose')
    parser.add_argument('-d', '--debug', action='store_true', default=False)
    parser.add_argument('--releases', type=str, nargs=1, help="release timeline")
    parser.add_argument('reportdir', type=str, nargs=1, help="dataset")
    args = parser.parse_args()

    reportdir = args.reportdir[0]
    picklefile = os.path.join(reportdir,'data.pickle')

    if os.path.exists(picklefile) :
        print "Skip parsing ", picklefile
        (switches,ar,sr) = pickle.load(open(picklefile,'r'))
    else :
        report = []
        switches = []
        for root, dirs, files in os.walk(reportdir, topdown=False):
            for name in fnmatch.filter(files, "*.yaml"):
                fname = os.path.join(root, name)
                print "Parse ", fname
                dataset = open(fname)
                r = parse(dataset)
                if r : 
                    switches.append(r['ocaml_switch'])
                    report.append(r)
                dataset.close()

        print "Aggregate ", picklefile
        (ar,sr) = aggregate(report)
        f = open(picklefile,'wb')
        pickle.dump((switches,ar,sr),f)
        f.close()

    print "Packages"
    html_package(ar,switches,sr['date'])
    print "Summary"
    html_summary(ar,sr,switches)
    print "Done"

    historydir = os.path.dirname(reportdir)
    picklehist = os.path.join(historydir,'history.pickle')

    print "Save History ", picklehist
    h = {}
    del sr['report']
    newdata = { 'switches' : switches , 'summary' : sr }
    newcommit = sr['commit'] 
    if os.path.exists(picklehist) :
        f = open(picklehist,'r')
        h = pickle.load(f)
        f.close()
        if not newcommit in h :
            h[newcommit] = newdata
            f = open(picklehist,'wb')
            pickle.dump(h,f)
            f.close()
    else :
        print "new hist", newcommit
        f = open(picklehist,'wb')
        h[newcommit] = newdata
        pickle.dump(h,f)
        f.close()
    print h

if __name__ == '__main__':
    main()
