function [trackers, ts]=sortTrackers(trackers,raw)
%by: Magnus Åberg

summary=tracker_summary2(trackers,raw);

ts = sortTable(summary,'intensity','descend');
II = (1:numel(ts.intensity))';
[~,order] = sort(ts.ID);
II = II(order);
c = getCounts(trackers(:,1),[1:max(trackers(:,1))]');
nds = [0; cumsum(c)];
for i = 1:numel(c)
    trackers(nds(i)+(1:c(i)),1)=II(i);
end

ts.ID = 1:numel( ts.ID );