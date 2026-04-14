function [rawThres] = thresholdRawData(raw,intensity_limit,varargin)

%by: Magnus Åberg

if nargin<3
    keepInds = find(raw.intensity_values>intensity_limit);
else
    switch(varargin{1})
        case {'<','<='}
            keepInds = find(raw.intensity_values<=intensity_limit);
    end
end

if isempty(keepInds)
    rawThres = [];
    return
end

keepMass = raw.mass_values(keepInds);

keepIntensity = raw.intensity_values(keepInds);
keepPoints = raw.points(keepInds);
nKeep = length(keepInds);

keepScanIndex = zeros(size(raw.scan_index));
k = 1;
n_scans = numel(keepScanIndex)-1;
for i = 2:n_scans,
   if k==0, k = 1; end
   while keepInds(k) < raw.scan_index(i)
      if k == nKeep
         break;
      end
      k = k+1;
   end
   if keepInds(k) > raw.scan_index(i),
      k = k-1;
   end
   keepScanIndex(i) = k;
end
keepScanIndex(end) = length(keepInds);

rawThres.mass_values = keepMass;
rawThres.intensity_values = keepIntensity;
rawThres.points = keepPoints;
rawThres.scan_index = keepScanIndex;
rawThres.scan_id = raw.scan_id;
rawThres.time_axis = raw.time_axis;
try
   rawThres.point_count = diff([keepScanIndex(:); numel(rawThres.mass_values)]);
   rawThres.info = raw.info;
   rawThres.info.intensity_threshold = intensity_limit;
end

if numel(rawThres.scan_index)~=numel(rawThres.scan_id)
   error([mfilename,': scan definition problem.']);
end