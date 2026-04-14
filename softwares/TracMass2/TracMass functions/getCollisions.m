function gid=getCollisions(peakList)
%gid=getCollisions(peakList)
% get globalID of clusters where there are more than one peak from a single
% sample.

%by: Magnus Åberg
nSamp = numel(unique(peakList.sample));

peakList = sortTable(peakList,'gid');

[C, ~, ref] = getCounts2(peakList.gid); %getCounts used until 2013-04-09
N = numel(ref);
S = cumsum([0;C(1:end-1)]);
a=S+1;b=S+C;
gid = false(N,1);
for i=1:N,
   scount(i,1) = numel(unique(peakList.sample(a(i):b(i)))) ;
   gid(i) = scount(i) < C(i);
end
gid = ref(gid);
