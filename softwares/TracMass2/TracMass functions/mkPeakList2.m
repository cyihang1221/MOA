function peakList =mkPeakList2(chrom,peakInds,gauss)

%by: Magnus Åberg

peakList.time = chrom.time(peakInds);

% smoothed estimate is better than just one point
x = maFilt(chrom.intensity(:),gauss(:));
peakList.intensity = x(peakInds);

% sometimes the smooth can be too intense, the following takes care of
% peaks more intense than the measured maximum value.
N = numel(chrom.time);
for i = 1:numel(peakInds)
   inds = peakInds(i)+(-1:1);
   inds(inds<1 | inds>N)=[];
   peakList.intensity(i) = min(peakList.intensity(i),max(chrom.intensity(inds)));
end

% moving average for the mass value of the peak
x = moving_average(chrom.mass,5);
peakList.mass = x(peakInds);


