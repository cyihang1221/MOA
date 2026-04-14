function [inds] = trimInds(inds,N)
%[inds] = trimInds(inds,N)
% N = length of vector
% returns inds in the range of [1..N]

%by: Magnus Åberg
inds(inds<1) = [];
inds(inds>N) = [];