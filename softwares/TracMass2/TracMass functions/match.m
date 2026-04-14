function [b,ia,ib] = match(idA,idB,valB)
%[b,ib] = match(idA,idB,valB)
% matches the ids of A and B and puts valB in the correct row of "A" where
% idB matches in idA. missing values become NaN's

%by: Magnus Åberg
b = nan(size(idA,1),size(valB,2));
warning('off','MATLAB:CELL:INTERSECT:RowsFlagIgnored')
[foo, ia,ib]= intersect(idA,idB,'rows');
warning('on' ,'MATLAB:CELL:INTERSECT:RowsFlagIgnored')
%b = nan(size(idA,1),size(valB,2));
b(ia,:) = valB(ib,:);

% checked - OK! /MÅ