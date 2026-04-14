function [c,inds,ref]=getCounts2(x)
% [c,inds,ref]=getCounts2(x)
% x - vector of values which are to be counted
% c - count data
% inds - start indices-1 for sorted x, use inds(i)+(1:c(i)) to retreive
% values
% ref - vector of reference values to get counts for

%by: Magnus Åberg
ref = unique(x);
x = sort(x(:));
c = diff([-inf;x(:)]);
inds = find(c)-1; % bug fix 2008-07-01 MÅ
c = diff([inds;numel(c)]);% % bug fix 2008-07-01 MÅ
