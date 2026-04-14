function [gid] = delaunay_align2(x,y)
%Magnus Åberg

gid = [];
%% delaunay triangulation
try
   t = DelaunayTri(x,y); % only on SU
catch
   t = delaunay(x,y); % buggy on SU
   %assert(numel(unique(t(:)))==numel(x)) % -- and on AZ it seems
end
%{
figure(1),clf,hold on
triplot(t,x,y)
plot(x,y,'r.')
%}
%% triangles to lines
lin  = [unique(t(:,[1 2]),'rows')
   unique(t(:,[1 3]),'rows')
   unique(t(:,[2 3]),'rows')];
%lin = unique(lin,'rows');
lin = ma_unique_rows(lin);
%whos t lin
%{
L = unique(sort(lin')','rows');
figure(2),clf,hold on
for i = 1:size(L,1)
  plot(x(L(i,:)),y(L(i,:)),'-')
end
plot(x,y,'r.')
%}
%% delete long lines
lin = del_lines(lin,x,y,1);

lin = ma_unique_rows([lin; fliplr(lin)]);
%{
L = unique(sort(lin')','rows');
figure(3),clf,hold on
for i = 1:size(L,1)
  plot(x(L(i,:)),y(L(i,:)),'-')
end
plot(x,y,'r.')
%}
%% find clusters
%clust = find_cluster2(lin,numel(x)); % works!
clust = find_cluster3(lin,numel(x));
%clust = find_cluster3_debug(lin,numel(x),x,y);
nClust = numel(unique(clust));
assert(nClust==max(clust)+any(clust==0));
%{
cmap = lines;
nc = size(cmap,1);
figure(4),clf,hold on
mask =clust == 0;
plot(x(mask),y(mask),'+','color',.5*ones(1,3),'markersize',4);
for i = 1:nClust
   mask = clust==i;
   plot(x(mask),y(mask),'.','color',cmap(mod(i,nc)+1,:));
end
%}
gid = clust;

