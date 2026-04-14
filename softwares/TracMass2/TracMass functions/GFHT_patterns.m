function [patterns times]=GFHT_patterns(peakList)
%Erik Tengstrand
gid = getPurePeaks(peakList);

nSamp = numel(unique(peakList.sample));
mapSamp(unique(peakList.sample)) = 1:nSamp;

X = zeros(nSamp,numel(gid));
for i = 1:numel(gid)
   mask = peakList.gid==gid(i);
   t = peakList.time(mask);
   s = peakList.sample(mask);
   X(mapSamp(s),i)=t;
end

patterns=X;
times=mean(X);

