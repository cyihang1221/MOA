function [gid]=getPurePeaks(peakList)
%[gid]=getPurePeaks(peakList)

%by: Magnus Åberg

nSamp = numel(unique(peakList.sample));

peakList = sortTable(peakList,'gid');

[C ref] = getCounts(peakList.gid);
N = numel(ref);
S = cumsum([0;C(1:end-1)]);
a=S+1;b=S+C;
gid = false(N,1);
for i=1:N,
   scount(i,1) = numel(unique(peakList.sample(a(i):b(i)))) ;
   gid(i) = numel(unique(peakList.sample(a(i):b(i)))) == nSamp && C(i)==nSamp;
end
gid = ref(gid);
%disp([ref scount scount>nSamp repmat(nSamp,N,1)])