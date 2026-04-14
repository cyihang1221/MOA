function x = ma_unique_rows(x)
%Magnus Åberg

[r,c] = size(x);
x = sortrows(x);
delmask = false(r,1);
for i = 2:r
   delmask(r) = all(x(r,:)==x(r-1,:));
end
   
x(delmask,:)=[];

