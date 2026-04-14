function varargout = plotPeakAlignment(peakList,timeFactor)
%by: Magnus Åberg

if nargin < 2
    timeFactor = 1;
end

peakList.time = peakList.time / timeFactor;
%figure(gcf)%,cla reset,hold on
hold on
cmap = lines(7);
nc = size(cmap,1);
peakList = sortTable(peakList,'gid');
mask = peakList.gid == 0;
plot(peakList.time(mask),peakList.mass(mask),'+','color',.5*ones(1,3),'markersize',4);
peakList = maskTable(peakList, ~mask );

[C I] = getCounts2(peakList.gid);
nClust = numel(C);
mm='^dxpsov+';
sz=[3 3 5 5 2 2 3 5];
lw=[.5 .5 2 .5 .5 .5 .5 2];

h = nan( nClust, 1 );
for i = 1:nClust
   im = mod(i,numel(mm))+1;
   ic = mod(i,nc)+1;
   inds = I(i) + (1:C(i));
   h( i ) = plot(peakList.time(inds),peakList.mass(inds),mm(im),...
       'color',cmap(ic,:),'markerfacecolor',cmap(ic,:),...
       'markersize',sz(im),'linewidth',lw(im));
end

if nargout > 0
    varargout{ 1 } = h;
end
