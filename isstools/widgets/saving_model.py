def model_to_dict(model):
    experiment_list = []
    for jj in range(model.rowCount()):
        experiment = OrderedDict()
        item = model.item(jj)
        experiment['repeat'] = item.repeat
        items = []
        for kk in range(item.rowCount()):
            step = item.child(kk)
            if step.item_type == 'sample':
                sample = OrderedDict()
                sample['name'] = step.name
                sample['x'] = step.x
                sample['y'] = step.y
                scans = []
                for ll in range(step.rowCount()):
                    substep = step.child(ll)
                    scan = {}
                    scan['scan_type'] = substep.scan_type
                    scans.append(scan)
                sample['scans'] = scans
                items.append(sample)

        experiment['items']= items
        experiment_list.append(experiment)

    return experiment_list



with open('moddic.json', 'xt') as f:
    json.dump(moddic, f)
