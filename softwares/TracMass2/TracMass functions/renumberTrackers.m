function [trackerList] = renumberTrackers(trackerList)
%by: Magnus Åberg
TRACKER_ID_COL = 1;
trackerIDs = unique(trackerList(:,TRACKER_ID_COL));
nPoints   = size(trackerList,1);
nTrackers = numel(trackerIDs);
iStart = 1;
newID = 1;
oldID = trackerIDs(newID);
for i = 2:nPoints,
   if trackerList(i,TRACKER_ID_COL) == oldID,
      % do nothing
   else
      iStop  = i-1;
      trackerList(iStart:iStop,TRACKER_ID_COL) = newID;
      iStart = i;
      newID  = newID+1;
      oldID  = trackerIDs(newID);
   end
end
% last tracker
trackerList(iStart:end,TRACKER_ID_COL) = newID;
