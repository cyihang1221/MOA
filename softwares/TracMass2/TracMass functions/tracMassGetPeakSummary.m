function [X,objLabel,varLabel,varID] = tracMassGetSummary3(db,transpose,consistencyLimit,intensityLimit)

%by: Magnus Åberg


if ~exist('transpose','var')
   transpose = false;
end
if ~exist('consistencyLimit','var')
   consistencyLimit = 0;
end
if ~exist('intensityLimit','var')
   intensityLimit = 0;
end
nObjects = numel(db.sample.id);
nTrackers = max(db.peakList.gid);

objLabel = cell(nObjects,1);
X = zeros(nObjects,nTrackers);
for i = 1:nObjects,
    % mask = db.peakList.sample == i; % BUG!
    mask = db.peakList.sample == db.sample.id(i); % ought to be correct
    mask = mask & db.peakList.gid > 0;

   X(i,db.peakList.gid(mask)) = db.peakList.intensity(mask);
   objLabel{i} = db.sample.name{i};
end

peakConsistency = getCounts(db.peakList.gid,1:max(db.peakList.gid))';
peakConsistency = peakConsistency / nObjects;
consistencyMask = peakConsistency >= consistencyLimit;
try
peakIntensity = max(X);
intensityMask = peakIntensity >= intensityLimit;
mask = intensityMask & consistencyMask;
catch
    keyboard
end

varLabel= cell(sum(mask),3);
k = 0;
ProgressHandle=waitbar(0,'Exporting data');
for i = 1:nTrackers,
    if mask(i)
        k = k+1;
        mm = db.peakList.gid==i;
        varLabel{k,1} = sprintf('ID%6i',i);
        varLabel{k,2} = sprintf('%9.4f',median(db.peakList.mass(mm)));
        varLabel{k,3} = sprintf('%5.2f',median(db.peakList.time(mm))); % print time in decimal minutes
        varLabel{k,4} = sprintf('%1i',max(db.peakList.binning(mm)));
    end
    waitbar(i/nTrackers,ProgressHandle)
end
delete(ProgressHandle)

X = X(:,mask);
varID = find(mask);

if transpose
   tmp = varLabel;
   varLabel = objLabel;
   objLabel = tmp;
   X = X';
end

